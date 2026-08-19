"""
gui.telas.t26_inventario.py
Tela T-26 — Sessões de inventário físico (MOD-07, Sprint 11).

Fluxo único em 3 estágios (abertura → coleta → fechamento), trocando o
conteúdo visível dentro do mesmo frame — a tela nunca é substituída pelo
roteador do app.py no meio de uma sessão, só ao entrar/sair de T-26.

Leitura na estação usa CampoBarras (mesmo componente HID de T-07/T-09).
Pareamento de dispositivo móvel é só a exibição do QR — a leitura vinda do
celular chega pelo ColetaWebService (fora do escopo desta rodada); nesta
tela o QR existe só para o operador escanear com o telefone.
"""
import io
import logging
import shutil
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
import segno
from PIL import Image

from gui.componentes.form_widgets import CampoBarras, FeedbackBanner
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
_PODE_GERENCIAR = ("admin", "ti")  # abrir/fechar/cancelar sessão (RF-39 + PermissionGuard)

_INTERVALO_POLL_MS = 4000


class TelaInventario(ctk.CTkFrame):
    """T-26 — abertura, coleta e fechamento de sessões de inventário físico."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._servico = InventarioService()
        self._patrimonio = PatrimonioService()
        self._pode_gerenciar = usuario.perfil.value in _PODE_GERENCIAR

        self._estagio = "abertura"
        self._sessao_id = None
        self._sessao = None
        self._localizacoes = []
        self._painel = None
        self._timer_poll = None
        self._decisoes: dict[int, AjusteConfirmado] = {}

        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        self._lbl_titulo = ctk.CTkLabel(self._topbar, text="Inventário",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color=COR_PETROLEO)
        self._lbl_titulo.pack(side="left", padx=16, pady=10)

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

    # ═══════════════════════════════════════════════════════════════════════
    # Estágio 1 — Abertura
    # ═══════════════════════════════════════════════════════════════════════

    def _mostrar_abertura(self):
        self._estagio = "abertura"
        self._sessao_id = None
        self._sessao = None
        self._limpar_conteudo()
        self._lbl_titulo.configure(text="Inventário — sessões")

        if self._pode_gerenciar:
            card = ctk.CTkFrame(self._conteudo, fg_color=COR_BRANCO, corner_radius=8,
                                border_width=1, border_color=COR_CINZA_B)
            card.pack(fill="x", padx=16, pady=(12, 8))
            ctk.CTkLabel(card, text="Nova sessão", font=ctk.CTkFont(size=13, weight="bold"),
                        text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(12, 6))

            linha = ctk.CTkFrame(card, fg_color="transparent")
            linha.pack(fill="x", padx=16)

            self._entry_desc = ctk.CTkEntry(linha, placeholder_text="Descrição da sessão",
                                            height=34, width=260, corner_radius=6)
            self._entry_desc.pack(side="left", padx=(0, 8))

            self._opt_escopo = ctk.CTkOptionMenu(
                linha, values=["Localização", "Geral"], width=140, height=34, corner_radius=6,
                fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color=COR_TEXTO,
                command=lambda _: self._ao_mudar_escopo())
            self._opt_escopo.pack(side="left", padx=(0, 8))

            labels_loc = [loc.nome_completo for loc in self._localizacoes] or ["—"]
            self._opt_localizacao_abertura = ctk.CTkOptionMenu(
                linha, values=labels_loc, width=220, height=34, corner_radius=6,
                fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color=COR_TEXTO,
                command=lambda _: self._atualizar_contagem_escopo())
            self._opt_localizacao_abertura.pack(side="left", padx=(0, 8))

            ctk.CTkButton(linha, text="Abrir sessão", width=130, height=34,
                         fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                         command=self._abrir_sessao).pack(side="left")

            self._lbl_contagem = ctk.CTkLabel(card, text="", text_color="#888780",
                                              font=ctk.CTkFont(size=11))
            self._lbl_contagem.pack(anchor="w", padx=16, pady=(6, 12))

            self._atualizar_contagem_escopo()

        # Lista de sessões
        ctk.CTkLabel(self._conteudo, text="Sessões", font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(8, 4))

        self._scroll_sessoes = ctk.CTkScrollableFrame(self._conteudo, fg_color=COR_BRANCO,
                                                       border_width=1, border_color=COR_CINZA_B,
                                                       corner_radius=0)
        self._scroll_sessoes.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._carregar_lista_sessoes()

    def _ao_mudar_escopo(self):
        habilitado = self._opt_escopo.get() == "Localização"
        self._opt_localizacao_abertura.configure(state="normal" if habilitado else "disabled")
        self._atualizar_contagem_escopo()

    def _atualizar_contagem_escopo(self):
        try:
            if self._opt_escopo.get() == "Geral":
                total = self._servico.contar_escopo("geral")
            else:
                loc = self._loc_id_por_label(self._opt_localizacao_abertura.get())
                total = self._servico.contar_escopo("localizacao", loc) if loc else 0
            self._lbl_contagem.configure(
                text=f"{total} bem(ns) ativo(s) serão incluídos no snapshot desta sessão.")
        except PatrimonioError as exc:
            self._lbl_contagem.configure(text=str(exc))

    def _loc_id_por_label(self, label: str):
        for loc in self._localizacoes:
            if loc.nome_completo == label:
                return loc.id
        return None

    def _abrir_sessao(self):
        descricao = self._entry_desc.get().strip()
        if not descricao:
            self._banner.erro("Informe uma descrição para a sessão.")
            return
        escopo = "geral" if self._opt_escopo.get() == "Geral" else "localizacao"
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

    def _carregar_lista_sessoes(self):
        for w in self._scroll_sessoes.winfo_children():
            w.destroy()
        try:
            sessoes = self._servico.listar_sessoes()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        if not sessoes:
            ctk.CTkLabel(self._scroll_sessoes, text="Nenhuma sessão de inventário registrada.",
                        text_color="#888780", font=ctk.CTkFont(size=12)).pack(pady=24)
            return

        for i, sessao in enumerate(sessoes):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll_sessoes, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            status_label = _STATUS_LABEL.get(sessao.status.value, sessao.status.value)
            fg_s, tc_s = _STATUS_COR.get(status_label, ("#F1EFE8", "#5F5E5A"))
            ctk.CTkLabel(row, text=status_label, fg_color=fg_s, text_color=tc_s,
                        font=ctk.CTkFont(size=9, weight="bold"), corner_radius=6,
                        padx=6, pady=2, width=80, height=24
                        ).pack(side="left", padx=(10, 8), pady=6)

            escopo_txt = "Geral" if sessao.escopo.value == "geral" else (
                sessao.localizacao.nome_completo if sessao.localizacao else "—")
            info = f"#{sessao.id} — {sessao.descricao}  ·  {escopo_txt}  ·  {sessao.aberto_em.strftime('%d/%m/%Y %H:%M')}"
            ctk.CTkLabel(row, text=info, text_color=COR_TEXTO, font=ctk.CTkFont(size=11),
                        anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=6)

            if sessao.status.value == "aberto":
                ctk.CTkButton(row, text="Retomar coleta", width=120, height=26,
                             fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                             font=ctk.CTkFont(size=10),
                             command=lambda sid=sessao.id: self._retomar_sessao(sid)
                             ).pack(side="right", padx=10, pady=4)
            else:
                ctk.CTkButton(row, text="Gerar relatório", width=120, height=26,
                             fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                             border_width=1, border_color=COR_CINZA_B,
                             hover_color=COR_CINZA_E, font=ctk.CTkFont(size=10),
                             command=lambda sid=sessao.id: self._gerar_relatorio(sid)
                             ).pack(side="right", padx=10, pady=4)

    def _retomar_sessao(self, sessao_id: int):
        self._sessao_id = sessao_id
        self._mostrar_coleta()

    # ═══════════════════════════════════════════════════════════════════════
    # Estágio 2 — Coleta
    # ═══════════════════════════════════════════════════════════════════════

    def _mostrar_coleta(self):
        self._estagio = "coleta"
        self._limpar_conteudo()

        try:
            self._sessao = self._servico.obter_sessao(self._sessao_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            self._mostrar_abertura()
            return

        self._lbl_titulo.configure(text=f"Inventário — coleta (sessão #{self._sessao_id})")

        header = ctk.CTkFrame(self._conteudo, fg_color=COR_BRANCO, corner_radius=8,
                              border_width=1, border_color=COR_CINZA_B)
        header.pack(fill="x", padx=16, pady=(12, 8))

        escopo_txt = "Geral" if self._sessao.escopo.value == "geral" else (
            self._sessao.localizacao.nome_completo if self._sessao.localizacao else "—")
        ctk.CTkLabel(header, text=f"{self._sessao.descricao}  ·  Escopo: {escopo_txt}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(12, 2))

        self._barra_progresso = ctk.CTkProgressBar(header, height=10, corner_radius=5,
                                                    progress_color=COR_PETROLEO_M)
        self._barra_progresso.pack(fill="x", padx=16, pady=(6, 2))
        self._lbl_progresso = ctk.CTkLabel(header, text="", text_color="#888780",
                                           font=ctk.CTkFont(size=11))
        self._lbl_progresso.pack(anchor="w", padx=16, pady=(0, 12))

        # Linha de leitura
        linha_leitura = ctk.CTkFrame(self._conteudo, fg_color=COR_BRANCO, corner_radius=8,
                                     border_width=1, border_color=COR_CINZA_B)
        linha_leitura.pack(fill="x", padx=16, pady=(0, 8))

        labels_loc = [loc.nome_completo for loc in self._localizacoes] or ["—"]
        self._opt_localizacao_coleta = ctk.CTkOptionMenu(
            linha_leitura, values=labels_loc, width=220, height=34, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color=COR_TEXTO)
        if self._sessao.escopo.value == "localizacao" and self._sessao.localizacao:
            self._opt_localizacao_coleta.set(self._sessao.localizacao.nome_completo)
            self._opt_localizacao_coleta.configure(state="disabled")
        self._opt_localizacao_coleta.grid(row=0, column=0, padx=(16, 8), pady=12)

        campo_leitura_wrap = ctk.CTkFrame(linha_leitura, fg_color="transparent")
        campo_leitura_wrap.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=12)
        linha_leitura.grid_columnconfigure(1, weight=1)
        self._campo_leitura = CampoBarras(
            campo_leitura_wrap, label="Tombo (leitor ou digitação)", obrigatorio=False,
            on_leitura=self._registrar_leitura, largura=260)
        self._campo_leitura.pack(fill="x")

        # Resultado da última leitura
        self._card_resultado = ctk.CTkFrame(self._conteudo, fg_color=COR_BRANCO, corner_radius=8,
                                            border_width=1, border_color=COR_CINZA_B)
        self._card_resultado.pack(fill="x", padx=16, pady=(0, 8))
        self._lbl_resultado = ctk.CTkLabel(self._card_resultado, text="Aguardando leitura...",
                                           text_color="#888780", font=ctk.CTkFont(size=12),
                                           anchor="w", justify="left", wraplength=760)
        self._lbl_resultado.pack(anchor="w", padx=16, pady=12, fill="x")

        # Ações
        acoes = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        acoes.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(acoes, text="Parear dispositivo móvel", width=180, height=32,
                     fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     command=self._abrir_painel_pareamento).pack(side="left", padx=(0, 8))
        ctk.CTkButton(acoes, text="Voltar para sessões", width=150, height=32,
                     fg_color=COR_BRANCO, text_color="#3d3d3a",
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     command=self._mostrar_abertura).pack(side="left", padx=(0, 8))
        if self._pode_gerenciar:
            ctk.CTkButton(acoes, text="Cancelar sessão", width=130, height=32,
                         fg_color=COR_BRANCO, text_color=COR_VERM,
                         border_width=1, border_color=COR_CINZA_B, hover_color=COR_VERM_BG,
                         command=self._confirmar_cancelar_sessao).pack(side="left", padx=(0, 8))
            ctk.CTkButton(acoes, text="Ir para fechamento →", width=170, height=32,
                         fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                         command=self._mostrar_fechamento).pack(side="right")

        # Sobras
        ctk.CTkLabel(self._conteudo, text="Sobras registradas", font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(4, 4))
        self._scroll_sobras = ctk.CTkScrollableFrame(self._conteudo, fg_color=COR_BRANCO,
                                                      border_width=1, border_color=COR_CINZA_B,
                                                      corner_radius=0, height=140)
        self._scroll_sobras.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._atualizar_progresso()
        self._campo_leitura.focus()
        self._agendar_poll()

    def _agendar_poll(self):
        self._timer_poll = self.after(_INTERVALO_POLL_MS, self._poll)

    def _poll(self):
        self._atualizar_progresso()
        self._agendar_poll()

    def _atualizar_progresso(self):
        try:
            resumo = self._servico.resumo_sessao(self._sessao_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._barra_progresso.set(resumo.progresso)
        self._lbl_progresso.configure(
            text=f"{resumo.conferidos}/{resumo.total_esperado} conferidos  ·  "
                 f"{resumo.encontrados} encontrados  ·  {resumo.divergentes} divergentes  ·  "
                 f"{resumo.sobras} sobra(s)")
        self._carregar_sobras()

    def _carregar_sobras(self):
        for w in self._scroll_sobras.winfo_children():
            w.destroy()
        try:
            sobras = self._servico.listar_sobras(self._sessao_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        if not sobras:
            ctk.CTkLabel(self._scroll_sobras, text="Nenhuma sobra registrada.",
                        text_color="#888780", font=ctk.CTkFont(size=11)).pack(pady=12)
            return
        for i, sobra in enumerate(sobras):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll_sobras, fg_color=bg, corner_radius=0)
            row.pack(fill="x")
            tipo_txt = "Não cadastrado" if sobra.tipo.value == "nao_cadastrado" else "Fora do escopo"
            ctk.CTkLabel(row, text=f"{sobra.codigo_lido}  ·  {tipo_txt}  ·  {sobra.localizacao.nome_completo}",
                        text_color=COR_TEXTO, font=ctk.CTkFont(size=11), anchor="w"
                        ).pack(side="left", fill="x", expand=True, padx=10, pady=6)
            ctk.CTkButton(row, text="Descartar", width=80, height=24,
                         fg_color=COR_BRANCO, text_color=COR_VERM,
                         border_width=1, border_color=COR_CINZA_B, hover_color=COR_VERM_BG,
                         font=ctk.CTkFont(size=10),
                         command=lambda sid=sobra.id: self._descartar_sobra(sid)
                         ).pack(side="right", padx=10, pady=4)

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

        fg, tc = _SEVERIDADE_COR.get(resultado.severidade.value, ("#F1EFE8", "#5F5E5A"))
        partes = [resultado.mensagem]
        if resultado.tombo:
            partes.insert(0, f"[{resultado.tombo}]")
        if resultado.localizacao_esperada:
            partes.append(f"Esperado: {resultado.localizacao_esperada}")
        self._card_resultado.configure(fg_color=fg)
        self._lbl_resultado.configure(text="  ·  ".join(partes), text_color=tc)

        self._barra_progresso.set(resultado.progresso)
        self._lbl_progresso.configure(
            text=f"{resultado.total_conferido}/{resultado.total_esperado} conferidos")

        self._campo_leitura.limpar()
        self._campo_leitura.focus()
        self._carregar_sobras()

    def _descartar_sobra(self, sobra_id: int):
        try:
            self._servico.descartar_sobra(sobra_id, self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._carregar_sobras()

    def _confirmar_cancelar_sessao(self):
        from tkinter import messagebox
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

    # ── Pareamento de dispositivo (painel flutuante) ─────────────────────────

    def _abrir_painel_pareamento(self):
        self._fechar_painel()
        self._painel = _PainelPareamento(
            self, servico=self._servico, usuario=self._usuario,
            sessao_id=self._sessao_id, localizacoes=self._localizacoes,
            on_fechar=self._fechar_painel,
        )
        self._painel.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5, relheight=0.6)

    # ═══════════════════════════════════════════════════════════════════════
    # Estágio 3 — Fechamento
    # ═══════════════════════════════════════════════════════════════════════

    def _mostrar_fechamento(self):
        self._estagio = "fechamento"
        self._decisoes = {}
        self._limpar_conteudo()
        self._lbl_titulo.configure(text=f"Inventário — fechamento (sessão #{self._sessao_id})")

        try:
            resumo = self._servico.resumo_sessao(self._sessao_id)
            divergentes = self._servico.listar_itens(self._sessao_id, "divergente_local")
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            self._mostrar_coleta()
            return

        aviso = ctk.CTkFrame(self._conteudo, fg_color=COR_AMBER_BG, corner_radius=8)
        aviso.pack(fill="x", padx=16, pady=(12, 8))
        ctk.CTkLabel(
            aviso, text=(f"{resumo.pendentes} bem(ns) ainda pendente(s) — ao fechar, viram "
                        "'não localizado' e o cadastro passa a 'em apuração'.")
            if resumo.pendentes else "Todos os bens do escopo já foram conferidos.",
            text_color=COR_AMBER_T, font=ctk.CTkFont(size=11), wraplength=760, justify="left",
        ).pack(anchor="w", padx=14, pady=10)

        ctk.CTkLabel(self._conteudo, text="Divergências pendentes de decisão (RN-14)",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(4, 4))

        scroll = ctk.CTkScrollableFrame(self._conteudo, fg_color=COR_BRANCO,
                                        border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        if not divergentes:
            ctk.CTkLabel(scroll, text="Nenhuma divergência nesta sessão.",
                        text_color="#888780", font=ctk.CTkFont(size=12)).pack(pady=20)
        else:
            for item in divergentes:
                self._linha_divergencia(scroll, item)

        rodape = ctk.CTkFrame(self._conteudo, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(rodape, text="← Voltar à coleta", width=140, height=34,
                     fg_color=COR_BRANCO, text_color="#3d3d3a",
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     command=self._mostrar_coleta).pack(side="left")
        ctk.CTkButton(rodape, text="Confirmar fechamento", width=180, height=34,
                     fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                     command=lambda: self._confirmar_fechamento(len(divergentes))
                     ).pack(side="right")

    def _linha_divergencia(self, parent, item):
        card = ctk.CTkFrame(parent, fg_color=COR_CINZA_E, corner_radius=6)
        card.pack(fill="x", padx=8, pady=6)

        loc_esp = item.localizacao_esperada.nome_completo if item.localizacao_esperada else "—"
        loc_enc = item.localizacao_encontrada.nome_completo if item.localizacao_encontrada else "—"
        ctk.CTkLabel(card, text=f"{item.bem.tombo} — {item.bem.descricao}",
                    font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_PETROLEO,
                    anchor="w").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(card, text=f"Esperado: {loc_esp}   →   Encontrado: {loc_enc}",
                    text_color="#5F5E5A", font=ctk.CTkFont(size=11), anchor="w"
                    ).pack(anchor="w", padx=12, pady=(0, 6))

        var_decisao = ctk.StringVar(value="")
        entry_obs = ctk.CTkEntry(card, placeholder_text="Observação (opcional)",
                                 height=28, corner_radius=6)

        def escolher(aplicar: bool):
            var_decisao.set("aplicar" if aplicar else "manter")
            self._decisoes[item.id] = AjusteConfirmado(
                inventario_item_id=item.id, aplicar=aplicar,
                observacao=entry_obs.get().strip() or None,
            )
            btn_aplicar.configure(fg_color=COR_PETROLEO_M if aplicar else COR_BRANCO,
                                  text_color=COR_BRANCO if aplicar else COR_PETROLEO_M)
            btn_manter.configure(fg_color=COR_PETROLEO_M if not aplicar else COR_BRANCO,
                                 text_color=COR_BRANCO if not aplicar else COR_PETROLEO_M)

        linha_btns = ctk.CTkFrame(card, fg_color="transparent")
        linha_btns.pack(fill="x", padx=12, pady=(0, 10))
        btn_aplicar = ctk.CTkButton(linha_btns, text="Mover para local encontrado", width=190,
                                    height=28, fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                                    border_width=1, border_color=COR_CINZA_B,
                                    font=ctk.CTkFont(size=10),
                                    command=lambda: escolher(True))
        btn_aplicar.pack(side="left", padx=(0, 6))
        btn_manter = ctk.CTkButton(linha_btns, text="Manter cadastro", width=140, height=28,
                                   fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                                   border_width=1, border_color=COR_CINZA_B,
                                   font=ctk.CTkFont(size=10),
                                   command=lambda: escolher(False))
        btn_manter.pack(side="left", padx=(0, 6))
        entry_obs.pack(side="left", fill="x", expand=True)

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


class _PainelPareamento(ctk.CTkFrame):
    """
    Painel flutuante: gera o token de pareamento (RF-36) e mostra o QR para
    o celular escanear. Não importa Modulo_06_dados nem repos — só chama o
    InventarioService já instanciado pela tela (Regra 1).
    """

    def __init__(self, master, servico, usuario, sessao_id, localizacoes, on_fechar):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=10,
                         border_width=1, border_color=COR_CINZA_B)
        self._servico = servico
        self._usuario = usuario
        self._sessao_id = sessao_id
        self._localizacoes = localizacoes
        self._on_fechar = on_fechar
        self._img_qr = None
        self._construir()

    def _construir(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(topo, text="Parear dispositivo móvel", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COR_PETROLEO).pack(side="left")
        ctk.CTkButton(topo, text="✕", width=28, height=28, fg_color="transparent",
                     text_color="#888780", hover_color=COR_CINZA_E,
                     command=self._on_fechar).pack(side="right")

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=20)

        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(fill="x", padx=20, pady=(4, 8))
        labels_loc = [loc.nome_completo for loc in self._localizacoes] or ["—"]
        self._opt_localizacao = ctk.CTkOptionMenu(
            linha, values=labels_loc, width=220, height=32, corner_radius=6,
            fg_color=COR_CINZA_E, button_color=COR_PETROLEO_M, text_color=COR_TEXTO)
        self._opt_localizacao.pack(side="left", padx=(0, 8))
        self._entry_label = ctk.CTkEntry(linha, placeholder_text="Nome do aparelho (opcional)",
                                         height=32, corner_radius=6)
        self._entry_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(self, text="Gerar QR de pareamento", height=32,
                     fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                     command=self._gerar).pack(padx=20, pady=(0, 10), fill="x")

        self._lbl_qr = ctk.CTkLabel(self, text="", fg_color=COR_CINZA_E)
        self._lbl_qr.pack(padx=20, pady=(0, 8))

        self._lbl_url = ctk.CTkLabel(self, text="", text_color="#5F5E5A",
                                     font=ctk.CTkFont(size=10), wraplength=380)
        self._lbl_url.pack(padx=20, pady=(0, 12))

        ctk.CTkButton(self, text="Revogar todos os tokens desta sessão", height=30,
                     fg_color=COR_BRANCO, text_color=COR_VERM,
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_VERM_BG,
                     command=self._revogar).pack(padx=20, pady=(0, 16), fill="x")

    def _loc_id(self):
        label = self._opt_localizacao.get()
        for loc in self._localizacoes:
            if loc.nome_completo == label:
                return loc.id
        return None

    def _gerar(self):
        loc_id = self._loc_id()
        if not loc_id:
            self._banner.erro("Selecione a localização do dispositivo.")
            return
        try:
            url = self._servico.parear_dispositivo(
                self._sessao_id, loc_id, self._usuario.id,
                dispositivo_label=self._entry_label.get().strip() or None,
            )
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao parear dispositivo: %s", exc)
            self._banner.erro(f"Erro ao parear dispositivo: {exc}")
            return

        try:
            qr = segno.make(url)
            buf = io.BytesIO()
            qr.save(buf, kind="png", scale=6, border=2)
            buf.seek(0)
            img = Image.open(buf)
            self._img_qr = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 220))
            self._lbl_qr.configure(image=self._img_qr, text="")
        except Exception as exc:
            logger.warning("Erro ao gerar imagem do QR: %s", exc)
            self._lbl_qr.configure(text="(não foi possível gerar a imagem do QR)")

        self._lbl_url.configure(text=url)
        self._banner.sucesso("Token gerado — escaneie o QR com o dispositivo.")

    def _revogar(self):
        try:
            total = self._servico.revogar_tokens(self._sessao_id, self._usuario.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._banner.sucesso(f"{total} token(s) revogado(s).")
        self._img_qr = None
        self._lbl_qr.configure(image=None, text="")
        self._lbl_url.configure(text="")
