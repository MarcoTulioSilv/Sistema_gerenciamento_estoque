"""
gui.telas.t26_inventario.py
Tela T-26 — Sessões de inventário físico (MOD-07, Sprint 11).

Fluxo em 3 estágios com stepper visual (Abertura → Coleta → Fechamento),
seguindo de perto o wireframe `Construção mod-07/wf-T26-T27.html`: cabeçalho
com trilha e ações por estágio, cartão de bipagem com log das últimas
leituras, painéis laterais de pendentes/pareamento/dispositivos na coleta, e
tabelas de divergências/não localizados/sobras no fechamento.

Leitura na estação usa CampoBarras (mesmo componente HID de T-07/T-09).
O QR de pareamento (lateral card) é um convite FIXO da sessão — não um
token de aparelho: exibi-lo de novo a cada montagem/retomada da tela não
cria nada no banco. Quem cria o pareamento real é o próprio celular, ao
confirmar o cadastro (nome + localização) depois de escanear o QR; só a
partir daí o aparelho aparece em "Dispositivos ativos". A leitura vinda do
celular chega pelo ColetaWebService.
"""
import io
import logging
import shutil
from tkinter import filedialog, messagebox

import customtkinter as ctk
import segno
from PIL import Image

from fuso_horario import formatar
from gui.componentes.form_widgets import CampoBarras, FeedbackBanner
from gui.componentes.tabela_scroll import TabelaScroll
from Modulo_07_patrimonio import (
    PatrimonioService, InventarioService, PatrimonioError,
    ContextoColeta, AjusteConfirmado,
)

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_PETROLEO_L, COR_CINZA_E, COR_CINZA_B,
    COR_BRANCO, COR_TEXTO, COR_VERM, COR_VERM_BG, COR_VERDE, COR_VERDE_BG,
    COR_VERDE_T, COR_AMBER_BG, COR_AMBER_T,
)

_STATUS_LABEL = {"aberto": "Aberta", "finalizado": "Finalizada", "cancelado": "Cancelada"}
_STATUS_COR = {
    "Aberta":     (COR_AMBER_BG, COR_AMBER_T),
    "Finalizada": (COR_VERDE_BG, COR_VERDE_T),
    "Cancelada":  (COR_VERM_BG, COR_VERM),
}
_SEVERIDADE_COR = {
    "ok":      (COR_VERDE_BG, COR_VERDE_T),
    "atencao": (COR_AMBER_BG, COR_AMBER_T),
    "erro":    (COR_VERM_BG, COR_VERM),
}
# Estilo do feedback grande da coleta — bg/faixa/título, igual ao wireframe
_FEEDBACK_ESTILO = {
    "ok":      dict(bg="#F1F9F2", faixa=COR_VERDE, titulo="#186B45"),
    "atencao": dict(bg="#FDF6EA", faixa="#BA7517", titulo="#7A4A08"),
    "erro":    dict(bg="#FCF0F0", faixa=COR_VERM, titulo="#7E2222"),
}
_TIPO_SOBRA_LABEL = {"nao_cadastrado": "Não cadastrado", "fora_escopo": "Fora de escopo"}
_TIPO_SOBRA_COR = {
    "nao_cadastrado": (COR_VERM_BG, COR_VERM),
    "fora_escopo":    (COR_AMBER_BG, COR_AMBER_T),
}

_PODE_GERENCIAR = ("admin", "ti")  # abrir/fechar/cancelar sessão (RF-39 + PermissionGuard)
_INTERVALO_POLL_MS = 4000
_MAX_LOG_LEITURAS = 8
_MAX_PENDENTES_VISIVEIS = 5


class TelaInventario(ctk.CTkFrame):
    """T-26 — abertura, coleta e fechamento de sessões de inventário físico."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._servico = InventarioService()
        self._patrimonio = PatrimonioService()
        self._pode_gerenciar = usuario.perfil.value in _PODE_GERENCIAR

        self._estagio_num = 1
        self._sessao_id = None
        self._sessao = None
        self._localizacoes = []
        self._painel = None
        self._timer_poll = None
        self._decisoes: dict[int, AjusteConfirmado] = {}
        self._mostrar_lista_sessoes = False
        self._img_qr = None

        # Cabeçalho persistente (título + trilha + ações), reconstruído por estágio
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                                    border_width=0)
        self._topbar.pack(fill="x")
        self._linha_topo = ctk.CTkFrame(self._topbar, fg_color="transparent")
        self._linha_topo.pack(fill="x", padx=22, pady=14)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

        self._conteudo = ctk.CTkFrame(self, fg_color="transparent")
        self._conteudo.pack(fill="both", expand=True)

        self._carregar_localizacoes()
        self._mostrar_abertura()

    # ── Infra comum ──────────────────────────────────────────────────────────

    def _limpar_conteudo(self):
        self._fechar_painel()
        if self._timer_poll is not None:
            self.after_cancel(self._timer_poll)
            self._timer_poll = None
        for w in self._conteudo.winfo_children():
            w.destroy()

    def _carregar_localizacoes(self):
        try:
            self._localizacoes = self._patrimonio.listar_localizacoes(self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            self._localizacoes = []

    def _fechar_painel(self):
        if self._painel is not None:
            self._painel.destroy()
            self._painel = None

    def _loc_id_por_label(self, label: str):
        for loc in self._localizacoes:
            if loc.nome_completo == label:
                return loc.id
        return None

    def _construir_cabecalho(self, titulo: str, trilha: str, acoes: list| None):
        """acoes: list de (texto, comando, primario_bool)."""
        for w in self._linha_topo.winfo_children():
            w.destroy()

        esquerda = ctk.CTkFrame(self._linha_topo, fg_color="transparent")
        esquerda.pack(side="left")
        ctk.CTkLabel(esquerda, text=titulo, font=ctk.CTkFont(size=24, weight="bold"),
                    text_color="#161614").pack(side="left")
        ctk.CTkLabel(esquerda, text=f"   {trilha}", text_color="#888780",
                    font=ctk.CTkFont(size=20)).pack(side="left")
        if acoes != None:
            direita = ctk.CTkFrame(self._linha_topo, fg_color="transparent")
            direita.pack(side="right")
        
            for texto, comando, primario in acoes:
                if primario:
                    ctk.CTkButton(direita, text=texto, height=30, fg_color=COR_PETROLEO_M,
                                hover_color=COR_PETROLEO, font=ctk.CTkFont(size=20),
                                command=comando).pack(side="left", padx=(8, 0))
                else:
                    ctk.CTkButton(direita, text=texto, height=30, fg_color=COR_BRANCO,
                                text_color="#161614", border_width=1, border_color=COR_CINZA_B,
                                hover_color=COR_CINZA_E, font=ctk.CTkFont(size=20),
                                command=comando).pack(side="left", padx=(8, 0))

    def _construir_stepper(self, parent, estagio_ativo: int):
        wrap = ctk.CTkFrame(parent, fg_color=COR_BRANCO, corner_radius=8,
                            border_width=1, border_color=COR_CINZA_B)
        wrap.pack(fill="x", padx=16, pady=(12, 8))
        linha = ctk.CTkFrame(wrap, fg_color="transparent")
        linha.pack(fill="x", padx=18, pady=12)

        for i, nome in enumerate(["Abertura", "Coleta", "Fechamento"], start=1):
            if i < estagio_ativo:
                cor_circulo, texto_num, cor_num = COR_VERDE, "✓", COR_BRANCO
            elif i == estagio_ativo:
                cor_circulo, texto_num, cor_num = COR_PETROLEO_M, str(i), COR_BRANCO
            else:
                cor_circulo, texto_num, cor_num = COR_CINZA_B, str(i), "#888780"
            cor_label = COR_PETROLEO if i == estagio_ativo else (
                "#3d3d3a" if i < estagio_ativo else "#888780")

            passo = ctk.CTkFrame(linha, fg_color="transparent")
            passo.pack(side="left")
            ctk.CTkLabel(passo, text=texto_num, width=34, height=34, corner_radius=17,
                        fg_color=cor_circulo, text_color=cor_num,
                        font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
            ctk.CTkLabel(passo, text=nome, text_color=cor_label,
                        font=ctk.CTkFont(size=18, weight="bold" if i == estagio_ativo else "normal")
                        ).pack(side="left", padx=(9, 0))
            if i < 3:
                ctk.CTkFrame(linha, height=2, fg_color=(COR_VERDE if i < estagio_ativo else COR_CINZA_B)
                            ).pack(side="left", fill="x", expand=True, padx=10)

    # ═══════════════════════════════════════════════════════════════════════
    # Estágio 1 — Abertura
    # ═══════════════════════════════════════════════════════════════════════

    def _mostrar_abertura(self):
        self._estagio_num = 1
        self._sessao_id = None
        self._sessao = None
        self._limpar_conteudo()
        self._construir_cabecalho(
            "Nova sessão de inventário", "Patrimônio › Inventário › Abertura",
           None)

        self._construir_stepper(self._conteudo, 1)

        if self._pode_gerenciar:
            card = ctk.CTkFrame(self._conteudo, fg_color=COR_BRANCO, corner_radius=8,
                                border_width=1, border_color=COR_CINZA_B)
            card.pack(fill="x", padx=16, pady=(0, 8))

            ctk.CTkLabel(card, text="ESCOPO DA CONFERÊNCIA", font=ctk.CTkFont(size=20, weight="bold"),
                        text_color=COR_PETROLEO).pack(anchor="w", padx=18, pady=(16, 10))

            linha_radio = ctk.CTkFrame(card, fg_color="transparent")
            linha_radio.pack(fill="x", padx=18)
            self._var_escopo = ctk.StringVar(value="localizacao")

            def _opcao_escopo(parent, valor, titulo, descricao):
                wrap = ctk.CTkFrame(parent, fg_color=COR_CINZA_E, corner_radius=7)
                wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))
                ctk.CTkRadioButton(wrap, text=titulo, variable=self._var_escopo, value=valor,
                                   font=ctk.CTkFont(size=19, weight="bold"),
                                   command=self._ao_mudar_escopo).pack(anchor="w", padx=12, pady=(10, 0))
                ctk.CTkLabel(wrap, text=descricao, text_color="#888780", font=ctk.CTkFont(size=13),
                            wraplength=260, justify="left", anchor="w"
                            ).pack(anchor="w", padx=28, pady=(2, 10))
                return wrap

            _opcao_escopo(linha_radio, "localizacao", "Por localização",
                         "Confere uma área. Outras áreas podem ser conferidas em paralelo.")
            _opcao_escopo(linha_radio, "geral", "Geral",
                         "Confere a clínica inteira. Bloqueia qualquer outra sessão enquanto aberta.")

            grid = ctk.CTkFrame(card, fg_color="transparent")
            grid.pack(fill="x", padx=18, pady=(16, 0))
            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, weight=1)

            campo_loc = ctk.CTkFrame(grid, fg_color="transparent")
            campo_loc.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
            ctk.CTkLabel(campo_loc, text="Localização", text_color="#888780",
                        font=ctk.CTkFont(size=20, weight="bold"), anchor="w").pack(fill="x")
            labels_loc = [loc.nome_completo for loc in self._localizacoes] or ["—"]
            self._opt_localizacao_abertura = ctk.CTkOptionMenu(
                campo_loc, values=labels_loc, height=34, corner_radius=6,
                fg_color=COR_CINZA_E, button_color=COR_PETROLEO_M, text_color=COR_TEXTO,
                command=lambda _: self._atualizar_contagem_escopo())
            self._opt_localizacao_abertura.pack(fill="x", pady=(5, 3))
            self._lbl_dica_localizacao = ctk.CTkLabel(campo_loc, text="", text_color="#ABA9A2",
                                                      font=ctk.CTkFont(size=13), anchor="w")
            self._lbl_dica_localizacao.pack(fill="x")

            campo_desc = ctk.CTkFrame(grid, fg_color="transparent")
            campo_desc.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
            ctk.CTkLabel(campo_desc, text="Descrição da sessão", text_color="#888780",
                        font=ctk.CTkFont(size=20, weight="bold"), anchor="w").pack(fill="x")
            self._entry_desc = ctk.CTkEntry(campo_desc, height=34, corner_radius=6,
                                            fg_color=COR_CINZA_E)
            self._entry_desc.pack(fill="x", pady=(5, 3))
            ctk.CTkLabel(campo_desc, text="Identifica a campanha nos relatórios e no histórico.",
                        text_color="#ABA9A2", font=ctk.CTkFont(size=13), anchor="w").pack(fill="x")

            rodape = ctk.CTkFrame(card, fg_color="transparent")
            rodape.pack(fill="x", padx=18, pady=(16, 18))
            ctk.CTkButton(rodape, text="Cancelar", height=34, fg_color=COR_BRANCO,
                         text_color="#3d3d3a", border_width=1, border_color=COR_CINZA_B,
                         hover_color=COR_CINZA_E,
                         command=lambda: (self._entry_desc.delete(0, "end"))).pack(side="left")
            ctk.CTkButton(rodape, text="Abrir sessão e iniciar coleta", height=34,
                         fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                         command=self._abrir_sessao).pack(side="right")

            self._atualizar_contagem_escopo()

        # Lista de sessões — colapsada por padrão, "Ver sessões anteriores" alterna
        self._frame_lista_sessoes = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        self._frame_lista_sessoes.pack(fill="both", expand=True, padx=0, pady=0)
        self._construir_lista_sessoes()

    #def _alternar_lista_sessoes(self):
    #    self._mostrar_lista_sessoes = not self._mostrar_lista_sessoes
    #    if self._mostrar_lista_sessoes:
    #        self._frame_lista_sessoes.pack(fill="both", expand=True, padx=0, pady=0)
    #        self._construir_lista_sessoes()
    #    else:
    #        self._frame_lista_sessoes.pack_forget()

    def _ao_mudar_escopo(self):
        habilitado = self._var_escopo.get() == "localizacao"
        self._opt_localizacao_abertura.configure(state="normal" if habilitado else "disabled")
        self._atualizar_contagem_escopo()

    def _atualizar_contagem_escopo(self):
        try:
            if self._var_escopo.get() == "geral":
                total = self._servico.contar_escopo("geral")
            else:
                loc = self._loc_id_por_label(self._opt_localizacao_abertura.get())
                total = self._servico.contar_escopo("localizacao", loc) if loc else 0
            if total == 0:
                self._lbl_dica_localizacao.configure(
                    text="Nenhum bem ativo neste escopo — a sessão pode ser aberta mesmo assim.",
                    text_color=COR_AMBER_T)
            else:
                self._lbl_dica_localizacao.configure(
                    text=f"{total} bem(ns) ativo(s) entrarão no snapshot.", text_color="#ABA9A2")
        except PatrimonioError as exc:
            self._lbl_dica_localizacao.configure(text=str(exc), text_color=COR_VERM)

    def _abrir_sessao(self):
        descricao = self._entry_desc.get().strip()
        if not descricao:
            self._banner.erro("Informe uma descrição para a sessão.")
            return
        escopo = self._var_escopo.get()
        loc_id = self._loc_id_por_label(self._opt_localizacao_abertura.get()) if escopo == "localizacao" else None
        if escopo == "localizacao" and not loc_id:
            self._banner.erro("Selecione uma localização.")
            return

        try:
            resultado = self._servico.abrir_sessao(descricao, escopo, self._usuario.id, loc_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao abrir sessão de inventário: %s", exc)
            self._banner.erro(f"Erro ao abrir sessão: {exc}")
            return

        for aviso in resultado.avisos:
            self._banner.aviso(aviso.mensagem)

        self._sessao_id = resultado.inventario_id
        self._mostrar_coleta()

    def _construir_lista_sessoes(self):
        for w in self._frame_lista_sessoes.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._frame_lista_sessoes, text="Sessões", font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(8, 4))
        scroll = ctk.CTkScrollableFrame(self._frame_lista_sessoes, fg_color=COR_BRANCO,
                                        border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        try:
            sessoes = self._servico.listar_sessoes()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        if not sessoes:
            ctk.CTkLabel(scroll, text="Nenhuma sessão de inventário registrada.",
                        text_color="#888780", font=ctk.CTkFont(size=22)).pack(pady=24)
            return

        for i, sessao in enumerate(sessoes):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            status_label = _STATUS_LABEL.get(sessao.status.value, sessao.status.value)
            fg_s, tc_s = _STATUS_COR.get(status_label, ("#F1EFE8", "#5F5E5A"))
            ctk.CTkLabel(row, text=status_label, fg_color=fg_s, text_color=tc_s,
                        font=ctk.CTkFont(size=16, weight="bold"), corner_radius=6,
                        padx=6, pady=2, width=130, height=32
                        ).pack(side="left", padx=(10, 8), pady=6)

            escopo_txt = "Geral" if sessao.escopo.value == "geral" else (
                sessao.localizacao.nome_completo if sessao.localizacao else "—")
            info = f"#{sessao.id} — {sessao.descricao}  ·  {escopo_txt}  ·  {formatar(sessao.aberto_em, '%d/%m/%Y %H:%M')}"
            ctk.CTkLabel(row, text=info, text_color=COR_TEXTO, font=ctk.CTkFont(size=20),
                        anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=6)

            if sessao.status.value == "aberto":
                ctk.CTkButton(row, text="Retomar coleta", width=180, height=34,
                             fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                             font=ctk.CTkFont(size=18),
                             command=lambda sid=sessao.id: self._retomar_sessao(sid)
                             ).pack(side="right", padx=10, pady=4)
            else:
                ctk.CTkButton(row, text="Gerar relatório", width=180, height=34,
                             fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                             border_width=1, border_color=COR_CINZA_B,
                             hover_color=COR_CINZA_E, font=ctk.CTkFont(size=18),
                             command=lambda sid=sessao.id: self._gerar_relatorio(sid)
                             ).pack(side="right", padx=10, pady=4)

    def _retomar_sessao(self, sessao_id: int):
        self._sessao_id = sessao_id
        self._mostrar_coleta()

    # ═══════════════════════════════════════════════════════════════════════
    # Estágio 2 — Coleta
    # ═══════════════════════════════════════════════════════════════════════

    def _mostrar_coleta(self):
        self._estagio_num = 2
        self._limpar_conteudo()

        try:
            self._sessao = self._servico.obter_sessao(self._sessao_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            self._mostrar_abertura()
            return

        acoes = [("Pausar e sair", self._mostrar_abertura, False)]
        if self._pode_gerenciar:
            acoes.append(("Ir para fechamento ›", self._mostrar_fechamento, True))
        self._construir_cabecalho(
            self._sessao.descricao, "Patrimônio › Inventário › Coleta", acoes)

        self._construir_stepper(self._conteudo, 2)

        corpo = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        corpo.grid_columnconfigure(0, weight=125)
        corpo.grid_columnconfigure(1, weight=75)
        corpo.grid_rowconfigure(0, weight=1)

        # ── Coluna esquerda: cartão de bipagem ──────────────────────────────
        bip = ctk.CTkFrame(corpo, fg_color=COR_BRANCO, corner_radius=8,
                           border_width=1, border_color=COR_CINZA_B)
        bip.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        topo_bip = ctk.CTkFrame(bip, fg_color=COR_PETROLEO, corner_radius=0)
        topo_bip.pack(fill="x")
        info_topo = ctk.CTkFrame(topo_bip, fg_color="transparent")
        info_topo.pack(side="left", padx=16, pady=0)
        loc_txt = "Geral" if self._sessao.escopo.value == "geral" else (
            self._sessao.localizacao.nome_completo if self._sessao.localizacao else "—")
        ctk.CTkLabel(info_topo, text=loc_txt, text_color=COR_BRANCO,
                    font=ctk.CTkFont(size=20, weight="bold"), anchor="w").pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(info_topo, text=f"Sessão #{self._sessao.id} · aberta em "
                                     f"{formatar(self._sessao.aberto_em, '%d/%m/%Y às %H:%M')}",
                    text_color="#CFE6E4", font=ctk.CTkFont(size=20), anchor="w").pack(anchor="w")
        self._lbl_contador_topo = ctk.CTkLabel(topo_bip, text="0 / 0", text_color=COR_BRANCO,
                                               font=ctk.CTkFont(size=20, weight="bold"))
        self._lbl_contador_topo.pack(side="right", padx=(0, 50), pady=0)
        ctk.CTkLabel(topo_bip, text="conferidos", text_color="#CFE6E4",
                    font=ctk.CTkFont(size=20)).pack(side="right", padx=(0, 15), pady=10)

        self._barra_progresso = ctk.CTkProgressBar(bip, height=6, corner_radius=0,
                                                    progress_color=COR_VERDE, fg_color="#173F3C")
        self._barra_progresso.pack(fill="x")
        self._barra_progresso.set(0)

        campo_wrap = ctk.CTkFrame(bip, fg_color="transparent")
        campo_wrap.pack(fill="x", padx=18, pady=(12, 0))
        ctk.CTkLabel(campo_wrap, text="Leitura", text_color="#888780",
                    font=ctk.CTkFont(size=20, weight="bold"), anchor="w").pack(fill="x")

        linha_campo = ctk.CTkFrame(campo_wrap, fg_color="transparent")
        linha_campo.pack(fill="x", pady=(0))
        labels_loc = [loc.nome_completo for loc in self._localizacoes] or ["—"]
        self._opt_localizacao_coleta = ctk.CTkOptionMenu(
            linha_campo, values=labels_loc, width=190, height=44, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color=COR_TEXTO)
        if self._sessao.escopo.value == "localizacao" and self._sessao.localizacao:
            self._opt_localizacao_coleta.set(self._sessao.localizacao.nome_completo)
            self._opt_localizacao_coleta.configure(state="disabled")
        self._opt_localizacao_coleta.pack(side="left", padx=(0, 8))

        self._campo_leitura = CampoBarras(
            linha_campo, label="", obrigatorio=False,
            on_leitura=self._registrar_leitura, largura=100)
        self._campo_leitura.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(campo_wrap, text="Leitor de código de barras, QR ou digitação do tombo. O "
                                      "campo limpa e volta ao foco sozinho após cada leitura.",
                    text_color="#ABA9A2", font=ctk.CTkFont(size=13), anchor="w"
                    ).pack(fill="x", pady=(0))

        # Resultado da leitura como "botão flutuante" (place, não pack): não
        # reserva espaço fixo no card enquanto aguarda a primeira leitura —
        # só aparece sobrepondo o canto inferior do card, via .place(), a
        # partir da primeira leitura (ver _registrar_leitura).
        self._card_resultado = ctk.CTkFrame(bip, width=340, fg_color="#F1EFE8",
                                            corner_radius=10, border_width=1, border_color=COR_CINZA_B)
        self._lbl_resultado_titulo = ctk.CTkLabel(self._card_resultado, text="",
                                                   text_color="#5F5E5A", font=ctk.CTkFont(size=24, weight="bold"),
                                                   anchor="w", wraplength=304)
        self._lbl_resultado_titulo.pack(anchor="w", fill="x", padx=18, pady=(12, 0))
        self._lbl_resultado_sub = ctk.CTkLabel(self._card_resultado, text="",
                                               text_color="#888780", font=ctk.CTkFont(size=20),
                                               anchor="w", wraplength=304)
        self._lbl_resultado_sub.pack(anchor="w", fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(bip, text="Últimas leituras", text_color="#888780",
                    font=ctk.CTkFont(size=18, weight="bold"), anchor="w"
                    ).pack(fill="x", padx=18, pady=(10, 4))
        self._frame_log = ctk.CTkFrame(bip, fg_color="transparent")
        self._frame_log.pack(fill="x", padx=0, pady=(0, 12))

        # ── Coluna direita: pendentes / parear / dispositivos ───────────────
        lateral = ctk.CTkFrame(corpo, fg_color="transparent")
        lateral.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._card_pendentes = ctk.CTkFrame(lateral, fg_color=COR_BRANCO, corner_radius=8,
                                            border_width=1, border_color=COR_CINZA_B)
        self._card_pendentes.pack(fill="x", pady=(0, 12))

        self._card_pareamento = ctk.CTkFrame(lateral, fg_color=COR_BRANCO, corner_radius=8,
                                             border_width=1, border_color=COR_CINZA_B)
        self._card_pareamento.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(self._card_pareamento, text="PAREAR CELULAR", font=ctk.CTkFont(size=20, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=14, pady=(12, 8))
        self._lbl_qr = ctk.CTkLabel(self._card_pareamento, text="", fg_color=COR_CINZA_E)
        self._lbl_qr.pack(padx=14, pady=(0, 6))
        self._lbl_qr_txt = ctk.CTkLabel(self._card_pareamento, text="", text_color="#888780",
                                        font=ctk.CTkFont(size=22), justify="center", wraplength=210)
        self._lbl_qr_txt.pack(padx=14, pady=(0, 14))

        self._card_dispositivos = ctk.CTkFrame(lateral, fg_color=COR_BRANCO, corner_radius=8,
                                               border_width=1, border_color=COR_CINZA_B)
        self._card_dispositivos.pack(fill="x")

        # Ações administrativas (cancelar sessão) — fora do wireframe, mas
        # necessário manter a capacidade de cancelar a partir da coleta.
        if self._pode_gerenciar:
            ctk.CTkButton(lateral, text="Cancelar sessão", height=34, fg_color=COR_BRANCO,
                         text_color=COR_VERM, border_width=1, border_color=COR_CINZA_B,
                         hover_color=COR_VERM_BG, font=ctk.CTkFont(size=18),
                         command=self._confirmar_cancelar_sessao).pack(fill="x", pady=(12, 0))

        self._atualizar_progresso()
        self._construir_pendentes()
        self._construir_dispositivos()
        self._atualizar_log()
        self._exibir_qr_convite()
        self._campo_leitura.focus()
        self._agendar_poll()

    def _agendar_poll(self):
        self._timer_poll = self.after(_INTERVALO_POLL_MS, self._poll)

    def _poll(self):
        self._atualizar_progresso()
        self._construir_pendentes()
        self._construir_dispositivos()
        self._atualizar_log()
        self._agendar_poll()

    def _atualizar_progresso(self):
        try:
            resumo = self._servico.resumo_sessao(self._sessao_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._barra_progresso.set(resumo.progresso)
        self._lbl_contador_topo.configure(text=f"{resumo.conferidos} / {resumo.total_esperado}")

    def _construir_pendentes(self):
        for w in self._card_pendentes.winfo_children():
            w.destroy()
        try:
            pendentes = self._servico.listar_itens(self._sessao_id, "pendente")
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        topo = ctk.CTkFrame(self._card_pendentes, fg_color="transparent")
        topo.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(topo, text="PENDENTES", font=ctk.CTkFont(size=20, weight="bold"),
                    text_color=COR_PETROLEO).pack(side="left")
        ctk.CTkLabel(topo, text=str(len(pendentes)), fg_color=COR_CINZA_E, text_color="#888780",
                    font=ctk.CTkFont(size=18, weight="bold"), corner_radius=8, padx=7
                    ).pack(side="right")

        if not pendentes:
            ctk.CTkLabel(self._card_pendentes, text="Nenhum item pendente.", text_color="#363634",
                        font=ctk.CTkFont(size=20)).pack(padx=14, pady=(0, 12))
            return 

        for item in pendentes[:_MAX_PENDENTES_VISIVEIS]:
            linha = ctk.CTkFrame(self._card_pendentes, fg_color="transparent")
            linha.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(linha, text=item.bem.tombo, text_color="#0B6D65", width=76, anchor="w",
                        font=ctk.CTkFont(size=27, weight="bold", family="Consolas")).pack(side="left")
            ctk.CTkLabel(linha, text=item.bem.descricao, text_color="#888780", anchor="e",
                        font=ctk.CTkFont(size=27)).pack(side="right", fill="x", expand=True)

        restantes = len(pendentes) - _MAX_PENDENTES_VISIVEIS
        if restantes > 0:
            ctk.CTkLabel(self._card_pendentes, text=f"+ {restantes} pendentes",
                        text_color="#ABA9A2", font=ctk.CTkFont(size=18)
                        ).pack(pady=(4, 12))
        else:
            ctk.CTkFrame(self._card_pendentes, fg_color="transparent", height=8).pack()

    def _construir_dispositivos(self):
        for w in self._card_dispositivos.winfo_children():
            w.destroy()
        try:
            dispositivos = self._servico.listar_dispositivos(self._sessao_id, self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        topo = ctk.CTkFrame(self._card_dispositivos, fg_color="transparent")
        topo.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(topo, text="DISPOSITIVOS ATIVOS", font=ctk.CTkFont(size=20, weight="bold"),
                    text_color=COR_PETROLEO).pack(side="left")
        ctk.CTkLabel(topo, text=str(len(dispositivos)), fg_color=COR_CINZA_E, text_color="#888780",
                    font=ctk.CTkFont(size=18, weight="bold"), corner_radius=8, padx=7
                    ).pack(side="right")

        if not dispositivos:
            ctk.CTkLabel(self._card_dispositivos, text="Nenhum dispositivo pareado.",
                        text_color="#888780", font=ctk.CTkFont(size=18)).pack(padx=14, pady=(0, 10))
        else:
            for token in dispositivos:
                linha = ctk.CTkFrame(self._card_dispositivos, fg_color="transparent")
                linha.pack(fill="x", padx=14, pady=3)
                ctk.CTkLabel(linha, text="●", text_color=COR_VERDE, font=ctk.CTkFont(size=16)
                            ).pack(side="left", padx=(0, 6))
                nome = token.dispositivo_label or f"Dispositivo #{token.id}"
                ctk.CTkLabel(linha, text=nome, text_color="#3d3d3a",
                            font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
                ctk.CTkLabel(linha, text=token.localizacao_conferida.nome_completo,
                            text_color="#888780", font=ctk.CTkFont(size=18)
                            ).pack(side="right")

        ctk.CTkButton(self._card_dispositivos, text="Revogar pareamentos", height=30,
                     fg_color=COR_BRANCO, text_color="#3d3d3a", border_width=1,
                     border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     font=ctk.CTkFont(size=18), command=self._revogar_pareamentos
                     ).pack(fill="x", padx=14, pady=(4, 14))

    def _revogar_pareamentos(self):
        try:
            total = self._servico.revogar_tokens(self._sessao_id, self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._banner.sucesso(f"{total} token(s) revogado(s).")
        self._construir_dispositivos()

    def _exibir_qr_convite(self):
        """
        QR fixo da sessão (convite) — não representa nenhum aparelho por si
        só, então é seguro chamar de novo a cada montagem/retomada da tela
        de coleta: sempre devolve a mesma URL, sem criar nada no banco. O
        aparelho só passa a existir (e aparecer em "Dispositivos ativos")
        quando o próprio celular confirma o cadastro.
        """
        try:
            url = self._servico.obter_convite(self._sessao_id, self._usuario.id)
        except PatrimonioError as exc:
            self._lbl_qr_txt.configure(text=str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao obter convite de pareamento: %s", exc)
            return

        try:
            qr = segno.make(url)
            buf = io.BytesIO()
            qr.save(buf, kind="png", scale=5, border=2)
            buf.seek(0)
            img = Image.open(buf)
            self._img_qr = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 150))
            self._lbl_qr.configure(image=self._img_qr, text="")
        except Exception as exc:
            logger.warning("Erro ao gerar imagem do QR: %s", exc)
            self._lbl_qr.configure(text="(QR indisponível)")

        self._lbl_qr_txt.configure(
            text="Aponte a câmera do celular para se cadastrar nesta sessão.")

    def _registrar_leitura(self, codigo: str):
        loc_id = self._loc_id_por_label(self._opt_localizacao_coleta.get())
        if not loc_id:
            self._banner.erro("Selecione a localização onde você está.")
            return
        contexto = ContextoColeta(
            inventario_id=self._sessao_id, localizacao_id=loc_id,
            usuario_id=self._usuario.id, origem="estacao",
        )
        try:
            resultado = self._servico.registrar_leitura(codigo, contexto)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            self._campo_leitura.limpar()
            self._campo_leitura.focus()
            return
        except Exception as exc:
            logger.error("Erro ao registrar leitura: %s", exc)
            self._banner.erro(f"Erro ao registrar leitura: {exc}")
            return

        estilo = _FEEDBACK_ESTILO.get(resultado.severidade.value, _FEEDBACK_ESTILO["atencao"])
        self._card_resultado.configure(fg_color=estilo["bg"])
        titulo = resultado.tombo or resultado.codigo_lido
        self._lbl_resultado_titulo.configure(text=f"{resultado.classificacao.value.replace('_', ' ').title()}"
                                                   f"  —  {titulo}", text_color=estilo["titulo"])
        self._lbl_resultado_sub.configure(text=resultado.mensagem)
        self._card_resultado.place(relx=1.0, rely=1.0, anchor="se", x=-16, y=-16)
        self._card_resultado.lift()

        self._barra_progresso.set(resultado.progresso)
        self._lbl_contador_topo.configure(text=f"{resultado.total_conferido} / {resultado.total_esperado}")

        self._campo_leitura.limpar()
        self._campo_leitura.focus()
        self._construir_pendentes()
        self._atualizar_log()

    def _atualizar_log(self):
        """
        Busca do banco as últimas leituras da sessão (encontrado/divergente/
        sobra) e re-renderiza — cobre leituras feitas na própria estação E
        as vindas de celulares pareados, que o processo desktop não tem
        como saber de outra forma (chamado tanto pelo polling quanto logo
        após uma leitura na estação, pra feedback imediato).
        """
        try:
            leituras = self._servico.listar_leituras_recentes(self._sessao_id, limite=_MAX_LOG_LEITURAS)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._renderizar_log(leituras)

    def _renderizar_log(self, leituras):
        for w in self._frame_log.winfo_children():
            w.destroy()
        if not leituras:
            ctk.CTkLabel(self._frame_log, text="Nenhuma leitura registrada ainda.",
                        text_color="#888780", font=ctk.CTkFont(size=20)).pack(padx=18, pady=4)
            return
        for i, leitura in enumerate(leituras):
            cor_fundo = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            cor_ponto = _SEVERIDADE_COR.get(leitura.severidade.value, (None, "#888780"))[1]
            bg_desc, fg_desc = _SEVERIDADE_COR.get(leitura.severidade.value, ("#F1EFE8", "#5F5E5A"))
            linha = ctk.CTkFrame(self._frame_log, fg_color=cor_fundo, corner_radius=0)
            linha.pack(fill="x")
            ctk.CTkLabel(linha, text="●", text_color=cor_ponto,
                        font=ctk.CTkFont(size=16)).pack(side="left", padx=(18, 8), pady=6)
            ctk.CTkLabel(linha, text=leitura.tombo or "—", text_color=COR_PETROLEO, width=76,
                        fg_color=COR_PETROLEO_L, corner_radius=6,
                        font=ctk.CTkFont(size=22, weight="bold", family="Consolas")
                        ).pack(side="left", padx=(0, 10), pady=6)
            ctk.CTkLabel(linha, text=leitura.descricao_bem.upper() or leitura.mensagem.upper(),
                        text_color=fg_desc, fg_color=bg_desc, corner_radius=6, anchor="w",
                        font=ctk.CTkFont(size=22, weight="bold")
                        ).pack(side="left", fill="x", expand=True, padx=(0, 10), pady=6)
            hora = formatar(leitura.quando, "%H:%M")
            ctk.CTkLabel(linha, text=hora, text_color="#ABA9A2", font=ctk.CTkFont(size=20)
                        ).pack(side="right", padx=(0, 18))
            

    def _confirmar_cancelar_sessao(self):
        if not messagebox.askyesno(
            "Cancelar sessão",
            "Cancelar esta sessão de inventário? As leituras já registradas "
            "permanecem no histórico, mas nenhum ajuste será aplicado."
        ):
            return
        try:
            self._servico.cancelar_sessao(self._sessao_id, "Cancelada pelo operador", self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._mostrar_abertura()

    # ═══════════════════════════════════════════════════════════════════════
    # Estágio 3 — Fechamento
    # ═══════════════════════════════════════════════════════════════════════

    def _mostrar_fechamento(self):
        self._estagio_num = 3
        self._decisoes = {}
        self._limpar_conteudo()

        try:
            self._sessao = self._servico.obter_sessao(self._sessao_id)
            resumo = self._servico.resumo_sessao(self._sessao_id)
            divergentes = self._servico.listar_itens(self._sessao_id, "divergente_local")
            pendentes = self._servico.listar_itens(self._sessao_id, "pendente")
            sobras = self._servico.listar_sobras(self._sessao_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            self._mostrar_coleta()
            return

        self._construir_cabecalho(
            f"Fechar — {self._sessao.descricao}", "Patrimônio › Inventário › Fechamento",
            [("‹ Voltar à coleta", self._mostrar_coleta, False),
             ("Baixar XLSX parcial", lambda: self._gerar_relatorio(self._sessao_id), False)])

        self._construir_stepper(self._conteudo, 3)

        # resumo-grid
        grid = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(0, 8))
        stats = [
            ("Esperados", resumo.total_esperado, "#3d3d3a"),
            ("Encontrados", resumo.encontrados, COR_VERDE),
            ("Divergentes", resumo.divergentes, "#BA7517"),
            ("Não localizados", resumo.nao_localizados, COR_VERM),
            ("Sobras", resumo.sobras, "#BA7517"),
        ]
        for i, (rotulo, valor, cor) in enumerate(stats):
            grid.grid_columnconfigure(i, weight=1)
            tile = ctk.CTkFrame(grid, fg_color=COR_BRANCO, corner_radius=8,
                                border_width=1, border_color=COR_CINZA_B)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            ctk.CTkLabel(tile, text=rotulo.upper(), text_color="#888780",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(12, 0))
            ctk.CTkLabel(tile, text=str(valor), text_color=cor,
                        font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(2, 12))

        if divergentes:
            aviso = ctk.CTkFrame(self._conteudo, fg_color=COR_AMBER_BG, corner_radius=6)
            aviso.pack(fill="x", padx=16, pady=(0, 12))
            ctk.CTkLabel(
                aviso, text=(f"{len(divergentes)} divergência(s) aguardam decisão. Nenhuma localização "
                            "é alterada automaticamente. O fechamento só é liberado depois que todas "
                            "tiverem uma escolha."),
                text_color=COR_AMBER_T, font=ctk.CTkFont(size=20), wraplength=900, justify="left",
            ).pack(anchor="w", padx=14, pady=10)

        scroll = ctk.CTkScrollableFrame(self._conteudo, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._construir_tabela_divergencias(scroll, divergentes)
        self._construir_tabela_nao_localizados(scroll, pendentes)
        self._construir_tabela_sobras(scroll, sobras)

        rodape = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(rodape, text="Cancelar sessão", height=34, fg_color=COR_BRANCO,
                     text_color=COR_VERM, border_width=1, border_color=COR_CINZA_B,
                     hover_color=COR_VERM_BG, command=self._confirmar_cancelar_sessao
                     ).pack(side="left")
        ctk.CTkButton(rodape, text="Salvar decisões", height=34, fg_color=COR_BRANCO,
                     text_color="#3d3d3a", border_width=1, border_color=COR_CINZA_B,
                     hover_color=COR_CINZA_E, command=self._salvar_decisoes_localmente
                     ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(rodape, text="Fechar sessão e gerar relatório", height=34,
                     fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                     command=lambda: self._confirmar_fechamento(len(divergentes))
                     ).pack(side="right")

    def _titulo_secao_tabela(self, parent, texto, badge_texto, badge_bg, badge_cor):
        linha = ctk.CTkFrame(parent, fg_color="transparent")
        linha.pack(fill="x", pady=(14, 6))
        ctk.CTkLabel(linha, text=texto, font=ctk.CTkFont(size=22, weight="bold"),
                    text_color="#161614").pack(side="left")
        ctk.CTkLabel(linha, text=badge_texto, fg_color=badge_bg, text_color=badge_cor,
                    font=ctk.CTkFont(size=16, weight="bold"), corner_radius=8, padx=8, pady=2
                    ).pack(side="left", padx=(8, 0))

    def _construir_tabela_divergencias(self, parent, divergentes):
        self._titulo_secao_tabela(parent, "Divergências de localização", "decisão obrigatória",
                                  COR_AMBER_BG, COR_AMBER_T)
        if not divergentes:
            ctk.CTkLabel(parent, text="Nenhuma divergência nesta sessão.", text_color="#888780",
                        font=ctk.CTkFont(size=20)).pack(anchor="w", pady=(0, 8))
            return

        tabela = TabelaScroll(parent, fg_color_grade=COR_BRANCO, border_width=1,
                              border_color=COR_CINZA_B, corner_radius=0)
        tabela.pack(fill="x", pady=(0, 4))
        tabela.configure(height=min(48 * (len(divergentes) + 1) + 10, 260))
        grade = tabela.grade
        colunas = [("Tombo", 90), ("Descrição", 220), ("Cadastrado em", 180),
                  ("Encontrado em", 180), ("Ajustar cadastro?", 160)]
        for col, (_, largura) in enumerate(colunas):
            grade.grid_columnconfigure(col, minsize=largura)
        for col, (nome, _) in enumerate(colunas):
            ctk.CTkLabel(grade, text=nome.upper(), text_color="#888780", fg_color=COR_CINZA_E,
                        font=ctk.CTkFont(size=16, weight="bold"), anchor="w"
                        ).grid(row=0, column=col, padx=10, pady=8, sticky="nsew")

        for i, item in enumerate(divergentes, 1):
            bg = COR_BRANCO if i % 2 == 1 else COR_CINZA_E
            loc_esp = item.localizacao_esperada.nome_completo if item.localizacao_esperada else "—"
            loc_enc = item.localizacao_encontrada.nome_completo if item.localizacao_encontrada else "—"
            ctk.CTkLabel(grade, text=item.bem.tombo, text_color=COR_PETROLEO, fg_color=bg, corner_radius= 5,
                        font=ctk.CTkFont(size=20, weight="bold", family="Consolas"), anchor="w"
                        ).grid(row=i, column=0, padx=10, pady=8, sticky="nsew")
            ctk.CTkLabel(grade, text=item.bem.descricao, text_color="#3d3d3a", fg_color=bg, corner_radius= 5,
                        font=ctk.CTkFont(size=20), anchor="center"
                        ).grid(row=i, column=1, padx=10, pady=8, sticky="nsew")
            ctk.CTkLabel(grade, text=loc_esp, text_color="#888780", fg_color=bg, corner_radius= 5,
                        font=ctk.CTkFont(size=20), anchor="center"
                        ).grid(row=i, column=2, padx=10, pady=8, sticky="nsew")
            ctk.CTkLabel(grade, text=loc_enc, text_color="#3d3d3a", fg_color=bg, corner_radius=5,
                        font=ctk.CTkFont(size=20, weight="bold"), anchor="center"
                        ).grid(row=i, column=3, padx=10, pady=8, sticky="nsew")

            wrap_escolha = ctk.CTkFrame(grade, fg_color=bg, corner_radius=5)
            wrap_escolha.grid(row=i, column=4, padx=10, pady=6, sticky="nsew")
            entry_obs = ctk.CTkEntry(grade, placeholder_text="Observação (opcional)", height=26,
                                     fg_color=bg, border_width=0)

            def escolher(aplicar, item_id=item.id, entry=entry_obs, btns_ref={}):
                self._decisoes[item_id] = AjusteConfirmado(
                    inventario_item_id=item_id, aplicar=aplicar,
                    observacao=entry.get().strip() or None,
                )
                btn_sim, btn_nao = btns_ref["sim"], btns_ref["nao"]
                btn_sim.configure(fg_color=COR_PETROLEO_M if aplicar else COR_BRANCO,
                                  text_color=COR_BRANCO if aplicar else "#3d3d3a")
                btn_nao.configure(fg_color="#888780" if not aplicar else COR_BRANCO,
                                  text_color=COR_BRANCO if not aplicar else "#3d3d3a")

            btns_ref = {}
            btn_sim = ctk.CTkButton(wrap_escolha, text="Sim", width=58, height=32,
                                    fg_color=COR_BRANCO, text_color="#3d3d3a", border_width=1,
                                    border_color=COR_CINZA_B, font=ctk.CTkFont(size=18),
                                    command=lambda: escolher(True, btns_ref=btns_ref))
            btn_sim.pack(side="left", padx=(0, 4))
            btn_nao = ctk.CTkButton(wrap_escolha, text="Não", width=58, height=32,
                                    fg_color=COR_BRANCO, text_color="#3d3d3a", border_width=1,
                                    border_color=COR_CINZA_B, font=ctk.CTkFont(size=18),
                                    command=lambda: escolher(False, btns_ref=btns_ref))
            btn_nao.pack(side="left")
            btns_ref["sim"], btns_ref["nao"] = btn_sim, btn_nao

    def _construir_tabela_nao_localizados(self, parent, pendentes):
        self._titulo_secao_tabela(parent, "Não localizados", 'irão para "Em apuração"',
                                  COR_VERM_BG, COR_VERM)
        if not pendentes:
            ctk.CTkLabel(parent, text="Nenhum item pendente — todo o escopo já foi conferido.",
                        text_color="#888780", font=ctk.CTkFont(size=20)).pack(anchor="w", pady=(0, 8))
            return

        tabela = TabelaScroll(parent, fg_color_grade=COR_BRANCO, border_width=1,
                              border_color=COR_CINZA_B, corner_radius=0)
        tabela.pack(fill="x", pady=(0, 4))
        tabela.configure(height=min(44 * (len(pendentes) + 1) + 10, 220))
        grade = tabela.grade
        colunas = [("Tombo", 90), ("Descrição", 260), ("Última localização", 200),
                  ("Situação após fechar", 180)]
        for col, (_, largura) in enumerate(colunas):
            grade.grid_columnconfigure(col, minsize=largura)
        for col, (nome, _) in enumerate(colunas):
            ctk.CTkLabel(grade, text=nome.upper(), text_color="#888780", fg_color=COR_CINZA_E, corner_radius=5,
                        font=ctk.CTkFont(size=16, weight="bold"), anchor="center"
                        ).grid(row=0, column=col, padx=10, pady=8, sticky="nsew")

        for i, item in enumerate(pendentes, 1):
            bg = COR_BRANCO if i % 2 == 1 else COR_CINZA_E
            ctk.CTkLabel(grade, text=item.bem.tombo, text_color=COR_PETROLEO, fg_color=bg, corner_radius=5,
                        font=ctk.CTkFont(size=20, weight="bold", family="Consolas"), anchor="center"
                        ).grid(row=i, column=0, padx=10, pady=6, sticky="nsew")
            ctk.CTkLabel(grade, text=item.bem.descricao, text_color="#3d3d3a", fg_color=bg, corner_radius=5,
                        font=ctk.CTkFont(size=20), anchor="center"
                        ).grid(row=i, column=1, padx=10, pady=6, sticky="nsew")
            ctk.CTkLabel(grade, text=item.localizacao_esperada.nome_completo if item.localizacao_esperada else "—", corner_radius=5,
                        text_color="#888780", fg_color=bg, font=ctk.CTkFont(size=20), anchor="center"
                        ).grid(row=i, column=2, padx=10, pady=6, sticky="nsew")
            wrap = ctk.CTkFrame(grade, fg_color="transparent")
            wrap.grid(row=i, column=3, padx=10, pady=6, sticky="nsew")
            ctk.CTkLabel(wrap, text="Em apuração", fg_color=COR_AMBER_BG, text_color=COR_AMBER_T, anchor="center",
                        font=ctk.CTkFont(size=16, weight="bold"), corner_radius=8, padx=8, pady=2
                        ).pack(anchor="center")

    def _construir_tabela_sobras(self, parent, sobras):
        self._titulo_secao_tabela(parent, "Sobras", "sem ação automática", "#F1EFE8", "#5F5E5A")
        if not sobras:
            ctk.CTkLabel(parent, text="Nenhuma sobra registrada.", text_color="#888780",
                        font=ctk.CTkFont(size=20)).pack(anchor="w", pady=(0, 8))
            return

        tabela = TabelaScroll(parent, fg_color_grade=COR_BRANCO, border_width=1,
                              border_color=COR_CINZA_B, corner_radius=0)
        tabela.pack(fill="x", pady=(0, 4))
        tabela.configure(height=min(44 * (len(sobras) + 1) + 10, 220))
        grade = tabela.grade
        colunas = [("Código lido", 130), ("Tipo", 150), ("Localização", 180), ("Ação", 100)]
        for col, (_, largura) in enumerate(colunas):
            grade.grid_columnconfigure(col, minsize=largura)
        for col, (nome, _) in enumerate(colunas):
            ctk.CTkLabel(grade, text=nome.upper(), text_color="#888780", fg_color=COR_CINZA_E, corner_radius=5, 
                        font=ctk.CTkFont(size=16, weight="bold"), anchor="center"
                        ).grid(row=0, column=col, padx=10, pady=8, sticky="nsew")

        for i, sobra in enumerate(sobras, 1):
            bg = COR_BRANCO if i % 2 == 1 else COR_CINZA_E
            ctk.CTkLabel(grade, text=sobra.codigo_lido, text_color=COR_PETROLEO, fg_color=bg,
                        font=ctk.CTkFont(size=20, weight="bold", family="Consolas"), anchor="center", corner_radius=5
                        ).grid(row=i, column=0, padx=10, pady=6, sticky="nsew")
            fg_t, tc_t = _TIPO_SOBRA_COR.get(sobra.tipo.value, ("#F1EFE8", "#5F5E5A"))
            wrap_tipo = ctk.CTkFrame(grade, fg_color=bg)
            wrap_tipo.grid(row=i, column=1, padx=10, pady=6, sticky="nsew")
            ctk.CTkLabel(wrap_tipo, text=_TIPO_SOBRA_LABEL.get(sobra.tipo.value, sobra.tipo.value), 
                        fg_color=fg_t, text_color=tc_t, font=ctk.CTkFont(size=16, weight="bold"),
                        corner_radius=8, padx=8, pady=2).pack(anchor="w")
            ctk.CTkLabel(grade, text=sobra.localizacao.nome_completo if sobra.localizacao else "—",
                        text_color="#888780", fg_color=bg, font=ctk.CTkFont(size=20), anchor="center"
                        ).grid(row=i, column=2, padx=10, pady=6, sticky="nsew")
            ctk.CTkButton(grade, text="Descartar", width=110, height=32, fg_color=bg,
                         text_color=COR_PETROLEO_M, border_width=1, border_color=COR_CINZA_B,
                         font=ctk.CTkFont(size=18),
                         command=lambda sid=sobra.id: self._descartar_sobra_fechamento(sid)
                         ).grid(row=i, column=3, padx=10, pady=4, sticky="w")

    def _descartar_sobra_fechamento(self, sobra_id: int):
        try:
            self._servico.descartar_sobra(sobra_id, self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._mostrar_fechamento()

    def _salvar_decisoes_localmente(self):
        self._banner.sucesso(f"{len(self._decisoes)} decisão(ões) salva(s) localmente — "
                             "feche a sessão para aplicar.")

    def _confirmar_fechamento(self, total_divergentes: int):
        if len(self._decisoes) < total_divergentes:
            self._banner.erro(
                f"Decida todas as divergências antes de fechar "
                f"({len(self._decisoes)}/{total_divergentes})."
            )
            return
        try:
            resumo = self._servico.fechar_sessao(
                self._sessao_id, list(self._decisoes.values()), self._usuario.id
            )
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao fechar sessão de inventário: %s", exc)
            self._banner.erro(f"Erro ao fechar sessão: {exc}")
            return

        self._banner.sucesso(
            f"Sessão fechada. {resumo.encontrados} encontrados, {resumo.divergentes} "
            f"divergências, {resumo.nao_localizados} não localizados."
        )
        self._gerar_relatorio(self._sessao_id)
        self._mostrar_abertura()

    # ── Relatório ─────────────────────────────────────────────────────────────

    def _gerar_relatorio(self, sessao_id: int):
        try:
            caminho = self._servico.gerar_relatorio(sessao_id, self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao gerar relatório de inventário: %s", exc)
            self._banner.erro(f"Erro ao gerar relatório: {exc}")
            return

        destino = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"inventario_{sessao_id}.xlsx")
        if destino:
            try:
                shutil.copy(caminho, destino)
                self._banner.sucesso(f"Relatório salvo em {destino}.")
            except OSError as exc:
                self._banner.erro(f"Erro ao salvar arquivo: {exc}")
        else:
            self._banner.sucesso(f"Relatório gerado — arquivo temporário em {caminho}.")

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def limpar_memoria(self):
        """Chamado pelo app.py ao sair da tela para esvaziar a RAM."""
        self._fechar_painel()
        if self._timer_poll is not None:
            self.after_cancel(self._timer_poll)
            self._timer_poll = None
