"""
gui.telas.t25_movimentacao_baixa.py
Tela T-25 — Movimentação, baixa e histórico de um bem patrimonial (MOD-07).
"""
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gui.componentes.form_widgets import Campo, FeedbackBanner
from Modulo_07_patrimonio import (
    PatrimonioService, DadosBem, DadosBaixa, PatrimonioError,
    AnexoObrigatorioError, AnexoInvalidoError, AnexoExcedidoError,
)
from gui.telas.t29_historico_manutencao import PainelHistoricoManutencao

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_PETROLEO_L, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM,
)

_SITUACAO_LABEL = {"ativo": "Ativo", "em_apuracao": "Em apuração", "baixado": "Baixado"}
_SITUACAO_COR = {
    "Ativo": ("#EAF3DE", "#27500A"),
    "Em apuração": ("#FAEEDA", "#854F0B"),
    "Baixado": ("#FCEBEB", "#A32D2D"),
}
_MOTIVOS_BAIXA = {
    "Descarte": "descarte", "Doação": "doacao", "Venda": "venda",
    "Extravio": "extravio", "Obsolescência": "obsolescencia", "Sinistro": "sinistro",
}
_TIPO_MOV_LABEL = {
    "cadastro": "Cadastro", "transferencia": "Transferência",
    "ajuste_inventario": "Ajuste de inventário", "baixa": "Baixa",
}


class TelaMovimentacaoBaixa(ctk.CTkFrame):
    """T-25 — transferir, baixar e ver histórico de um bem (RF-29, RF-30)."""

    def __init__(self, master, usuario, on_navigate, bem_id: int):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._bem_id = bem_id
        self._servico = PatrimonioService()
        self._bem = None
        self._localizacoes = []
        self._aba_atual = "transferir"
        self._pode_baixar = usuario.perfil.value in ("admin", "ti")
        self._anexo_bytes: bytes | None = None
        self._anexo_nome: str | None = None
        self._card_baixa_info = None
        self._painel_manutencao = None
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        self._lbl_titulo = ctk.CTkLabel(self._topbar, text="Movimentar bem",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color=COR_PETROLEO)
        self._lbl_titulo.pack(side="left", padx=16)
        ctk.CTkLabel(self._topbar, text="Patrimônio › Bens › Movimentar",
                     font=ctk.CTkFont(size=11), text_color="#888780").pack(side="left", padx=4)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        corpo.grid_columnconfigure(0, weight=6)
        corpo.grid_columnconfigure(1, weight=4)
        corpo.grid_rowconfigure(0, weight=1)

        # ── Coluna esquerda: abas + formulários ─────────────────────────────────
        self._esquerda = ctk.CTkScrollableFrame(corpo, fg_color="transparent")
        self._esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        esquerda = self._esquerda

        self._abas_frame = ctk.CTkFrame(esquerda, fg_color="transparent")
        self._abas_frame.pack(fill="x", pady=(0, 8))
        self._botoes_aba = {}
        self._construir_botao_aba("transferir", "Transferir")
        if self._pode_baixar:
            self._construir_botao_aba("baixar", "Baixar")
        self._construir_botao_aba("editar", "Editar dados")

        self._frame_transferir = self._construir_form_transferir(esquerda)
        self._frame_baixar = self._construir_form_baixar(esquerda) if self._pode_baixar else None
        self._frame_editar = self._construir_form_editar(esquerda)

        self._lbl_baixado = ctk.CTkLabel(
            esquerda, text="Bem baixado — operações de transferência, baixa e edição indisponíveis (RN-12).",
            text_color=COR_VERM, font=ctk.CTkFont(size=12), wraplength=420, justify="left")

        # ── Coluna direita: resumo + histórico ──────────────────────────────────
        direita = ctk.CTkFrame(corpo, fg_color="transparent")
        direita.grid(row=0, column=1, sticky="nsew")

        self._resumo_card = ctk.CTkFrame(direita, fg_color=COR_BRANCO, corner_radius=8,
                                         border_width=1, border_color=COR_CINZA_B)
        self._resumo_card.pack(fill="x", pady=(0, 14))
        self._construir_resumo(self._resumo_card)

        hist_card = ctk.CTkFrame(direita, fg_color=COR_BRANCO, corner_radius=8,
                                 border_width=1, border_color=COR_CINZA_B)
        hist_card.pack(fill="both", expand=True)
        ctk.CTkLabel(hist_card, text="HISTÓRICO · SOMENTE LEITURA", text_color=COR_PETROLEO,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkFrame(hist_card, fg_color=COR_CINZA_B, height=1).pack(fill="x", padx=14, pady=(0, 6))
        self._historico_scroll = ctk.CTkScrollableFrame(hist_card, fg_color="transparent")
        self._historico_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self._mostrar_aba("transferir")

    def _construir_botao_aba(self, nome: str, texto: str):
        btn = ctk.CTkButton(self._abas_frame, text=texto, height=30, corner_radius=6,
                            fg_color="transparent", text_color=COR_PETROLEO,
                            border_width=1, border_color=COR_CINZA_B,
                            command=lambda: self._mostrar_aba(nome))
        btn.pack(side="left", padx=(0, 6))
        self._botoes_aba[nome] = btn

    def _construir_form_transferir(self, master) -> ctk.CTkFrame:
        card = ctk.CTkFrame(master, fg_color=COR_BRANCO, corner_radius=8,
                            border_width=1, border_color=COR_CINZA_B)

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(16, 8))
        grid.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(grid, text="Localização atual", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        self._lbl_localizacao_atual = ctk.CTkLabel(grid, text="—", text_color="#3d3d3a",
                                                    font=ctk.CTkFont(size=12), anchor="w")
        self._lbl_localizacao_atual.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkLabel(grid, text="Nova localização*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(row=0, column=1, sticky="w")
        self._opt_destino = ctk.CTkOptionMenu(grid, values=["Carregando..."], width=200, height=32,
                                              fg_color=COR_CINZA_E, button_color=COR_PETROLEO_M, text_color="#3d3d3a")
        self._opt_destino.grid(row=1, column=1, sticky="ew", pady=(4, 0))

        ctk.CTkLabel(card, text="Motivo*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(anchor="w", padx=16, pady=(10, 3))
        self._txt_motivo_transf = ctk.CTkTextbox(card, height=50, corner_radius=6, fg_color=COR_CINZA_E, text_color="#3d3d3a")
        self._txt_motivo_transf.pack(fill="x", padx=16)
        ctk.CTkLabel(card, text="Fica no histórico permanente do bem e não pode ser editado depois.",
                     text_color="#ABA9A2", font=ctk.CTkFont(size=10), anchor="w").pack(anchor="w", padx=16, pady=(2, 12))

        rodape = ctk.CTkFrame(card, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(rodape, text="Confirmar transferência", width=200, height=34,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      command=self._confirmar_transferencia).pack(side="right")
        return card

    def _construir_form_baixar(self, master) -> ctk.CTkFrame:
        card = ctk.CTkFrame(master, fg_color=COR_BRANCO, corner_radius=8,
                            border_width=1, border_color="#EDC9C9")

        alerta = ctk.CTkFrame(card, fg_color="#FCEBEB", corner_radius=6)
        alerta.pack(fill="x", padx=16, pady=(16, 10))
        ctk.CTkLabel(alerta, text="A baixa é irreversível pela interface. O bem sai do escopo de "
                                  "inventários futuros e permanece consultável apenas para auditoria.",
                     text_color="#7E2222", font=ctk.CTkFont(size=11), wraplength=380,
                     justify="left").pack(padx=10, pady=8, anchor="w")

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(0, 8))
        grid.grid_columnconfigure((0, 1, 2), weight=1, minsize=120)

        ctk.CTkLabel(grid, text="Motivo*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(row=0, column=0, sticky="nw", pady=(0,3))
        self._opt_motivo_baixa = ctk.CTkOptionMenu(grid, values=list(_MOTIVOS_BAIXA.keys()),
                                                    width=140, height=32, fg_color=COR_CINZA_E,
                                                    button_color=COR_PETROLEO_M,text_color="#3d3d3a")
        self._opt_motivo_baixa.grid(row=0, column=0, sticky="sw", pady=(4, 0), padx=(0,8))

        self._campo_data_baixa = Campo(grid, "Data da baixa", largura=60, placeholder="dd/mm/aaaa")
        self._campo_data_baixa.grid(row=0, column=1, rowspan=2, sticky="ew", padx=(0, 8))
        self._campo_data_baixa.set(date.today().strftime("%d/%m/%Y"))

        self._campo_documento = Campo(grid, "Referência (ata/termo/processo)", largura=140)
        self._campo_documento.grid(row=0, column=2, rowspan=2, sticky="ew")

        grid2 = ctk.CTkFrame(card, fg_color="transparent")
        grid2.pack(fill="x", padx=16, pady=(8, 0))
        grid2.grid_columnconfigure((0, 1), weight=1)

        self._campo_mtr = Campo(grid2, "Número MTR", largura=140)
        self._campo_mtr.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._campo_laudo = Campo(grid2, "Número do laudo", largura=140)
        self._campo_laudo.grid(row=0, column=1, sticky="ew")

        anexo_frame = ctk.CTkFrame(card, fg_color=COR_CINZA_E, corner_radius=6)
        anexo_frame.pack(fill="x", padx=16, pady=(12, 8))
        ctk.CTkLabel(anexo_frame, text="Anexo em PDF*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(anchor="w", padx=10, pady=(8, 4))
        linha_anexo = ctk.CTkFrame(anexo_frame, fg_color="transparent")
        linha_anexo.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(linha_anexo, text="Selecionar arquivo…", width=140, height=28,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                      font=ctk.CTkFont(size=11), command=self._selecionar_anexo_pdf).pack(side="left")
        self._lbl_anexo = ctk.CTkLabel(linha_anexo, text="Nenhum arquivo selecionado.",
                                       text_color="#888780", font=ctk.CTkFont(size=11))
        self._lbl_anexo.pack(side="left", padx=10)

        rodape = ctk.CTkFrame(card, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(8, 16))
        ctk.CTkButton(rodape, text="Registrar baixa", width=160, height=34,
                      fg_color=COR_BRANCO, text_color=COR_VERM,
                      border_width=1, border_color="#E9C9C9", hover_color="#FCEBEB",
                      command=self._confirmar_baixa).pack(side="right")
        return card

    def _construir_form_editar(self, master) -> ctk.CTkFrame:
        card = ctk.CTkFrame(master, fg_color=COR_BRANCO, corner_radius=8,
                            border_width=1, border_color=COR_CINZA_B)

        self._campo_descricao = Campo(card, "Descrição", obrigatorio=True, largura=380)
        self._campo_descricao.pack(fill="x", padx=16, pady=(16, 8))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(0, 8))
        grid.grid_columnconfigure((0, 1, 2), weight=1)
        self._campo_marca = Campo(grid, "Marca / modelo", largura=140)
        self._campo_marca.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._campo_data_aq = Campo(grid, "Data de aquisição", placeholder="dd/mm/aaaa", largura=120)
        self._campo_data_aq.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self._campo_valor = Campo(grid, "Valor de aquisição", placeholder="0,00", largura=120)
        self._campo_valor.grid(row=0, column=2, sticky="ew")

        self._campo_nf = Campo(card, "Nota fiscal", largura=200)
        self._campo_nf.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(card, text="Observação", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(anchor="w", padx=16, pady=(2, 3))
        self._txt_observacao = ctk.CTkTextbox(card, height=60, corner_radius=6, fg_color=COR_CINZA_E)
        self._txt_observacao.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(card, text="Mudança de lotação é feita na aba Transferir — edição não move o bem.",
                     text_color="#ABA9A2", font=ctk.CTkFont(size=10), anchor="w").pack(anchor="w", padx=16, pady=(0, 12))

        rodape = ctk.CTkFrame(card, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(rodape, text="Salvar alterações", width=160, height=34,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      command=self._confirmar_edicao).pack(side="right")
        return card

    def _construir_resumo(self, master):
        topo = ctk.CTkFrame(master, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(14, 4))
        self._lbl_tombo_resumo = ctk.CTkLabel(topo, text="—", text_color=COR_PETROLEO,
                                              font=ctk.CTkFont(size=16, weight="bold", family="Consolas"))
        self._lbl_tombo_resumo.pack(side="left")
        self._lbl_situacao_resumo = ctk.CTkLabel(topo, text="", corner_radius=6, padx=8, pady=2,
                                                 font=ctk.CTkFont(size=10, weight="bold"))
        self._lbl_situacao_resumo.pack(side="left", padx=8)

        self._lbl_desc_resumo = ctk.CTkLabel(master, text="", text_color="#3d3d3a",
                                             font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
        self._lbl_desc_resumo.pack(fill="x", padx=16, pady=(0, 10))

        self._linhas_resumo_frame = ctk.CTkFrame(master, fg_color="transparent")
        self._linhas_resumo_frame.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(master, text="Histórico de manutenção", height=28,
                      fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._abrir_historico_manutencao).pack(fill="x", padx=16, pady=(0, 14))

    def _mostrar_aba(self, nome: str):
        if self._bem and self._bem.situacao.value == "baixado":
            return
        self._aba_atual = nome
        for aba, btn in self._botoes_aba.items():
            ativo = aba == nome
            btn.configure(fg_color=COR_BRANCO if ativo else COR_CINZA_B,
                          text_color=COR_PETROLEO, border_color=COR_CINZA_B if ativo else COR_CINZA_E,
                          font=ctk.CTkFont(size=12, weight="bold" if ativo else "normal"))

        for frame in (self._frame_transferir, self._frame_baixar, self._frame_editar):
            if frame:
                frame.pack_forget()

        alvo = {"transferir": self._frame_transferir, "baixar": self._frame_baixar,
                "editar": self._frame_editar}.get(nome)
        if alvo:
            alvo.pack(fill="x")

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        try:
            self._bem = self._servico.obter_bem(self._usuario.id, self._bem_id)
            self._localizacoes = self._servico.listar_localizacoes(self._usuario.id)
        except PatrimonioError as exc:
            logger.error("Erro ao carregar bem %s: %s", self._bem_id, exc)
            self._banner.erro(str(exc))
            return

        try:
            historico_manut = self._servico.historico_manutencao(self._usuario.id, self._bem_id)
            self._ultima_manutencao = historico_manut[-1].data_manutencao if historico_manut else None
        except PatrimonioError:
            self._ultima_manutencao = None

        self._lbl_titulo.configure(text=f"{self._bem.tombo} — {self._bem.descricao}")
        self._preencher_resumo()
        self._preencher_historico()

        if self._bem.situacao.value == "baixado":
            self._abas_frame.pack_forget()
            self._frame_transferir.pack_forget()
            if self._frame_baixar:
                self._frame_baixar.pack_forget()
            self._frame_editar.pack_forget()
            self._lbl_baixado.pack(anchor="w", pady=(0, 12))
            self._mostrar_info_baixa()
            return

        # Combo de destino: todas as localizações, exceto a atual.
        labels_destino = [loc.nome_completo for loc in self._localizacoes if loc.id != self._bem.localizacao_id]
        self._opt_destino.configure(values=labels_destino or ["Nenhuma outra localização"])
        if labels_destino:
            self._opt_destino.set(labels_destino[0])
        self._lbl_localizacao_atual.configure(
            text=self._bem.localizacao.nome_completo if self._bem.localizacao else "—")

        self._campo_descricao.set(self._bem.descricao)
        if self._bem.marca_modelo:
            self._campo_marca.set(self._bem.marca_modelo)
        if self._bem.data_aquisicao:
            self._campo_data_aq.set(self._bem.data_aquisicao.strftime("%d/%m/%Y"))
        if self._bem.valor_aquisicao is not None:
            self._campo_valor.set(str(self._bem.valor_aquisicao))
        if self._bem.nota_fiscal:
            self._campo_nf.set(self._bem.nota_fiscal)
        if self._bem.observacao:
            self._txt_observacao.insert("1.0", self._bem.observacao)

    def _preencher_resumo(self):
        bem = self._bem
        self._lbl_tombo_resumo.configure(text=bem.tombo)
        situacao_label = _SITUACAO_LABEL.get(bem.situacao.value, bem.situacao.value)
        fg, tc = _SITUACAO_COR.get(situacao_label, ("#F1EFE8", "#5F5E5A"))
        self._lbl_situacao_resumo.configure(text=situacao_label, fg_color=fg, text_color=tc)
        self._lbl_desc_resumo.configure(text=bem.descricao)

        for w in self._linhas_resumo_frame.winfo_children():
            w.destroy()

        linhas = [
            ("Marca / modelo", bem.marca_modelo or "—"),
            ("Localização", bem.localizacao.nome_completo if bem.localizacao else "—"),
            ("Aquisição", bem.data_aquisicao.strftime("%d/%m/%Y") if bem.data_aquisicao else "—"),
            ("Valor", f"R$ {bem.valor_aquisicao:.2f}" if bem.valor_aquisicao is not None else "—"),
            ("Nota fiscal", bem.nota_fiscal or "—"),
            ("Última manutenção",
             self._ultima_manutencao.strftime("%d/%m/%Y") if self._ultima_manutencao else "Nunca"),
        ]
        for i, (k, v) in enumerate(linhas):
            linha = ctk.CTkFrame(self._linhas_resumo_frame, fg_color="transparent")
            linha.pack(fill="x", pady=3)
            if i > 0:
                ctk.CTkFrame(self._linhas_resumo_frame, fg_color=COR_CINZA_E, height=1).pack(fill="x")
            ctk.CTkLabel(linha, text=k, text_color="#888780", font=ctk.CTkFont(size=11),
                         width=110, anchor="w").pack(side="left")
            ctk.CTkLabel(linha, text=v, text_color="#3d3d3a", font=ctk.CTkFont(size=11),
                         anchor="w").pack(side="left")

    def _preencher_historico(self):
        for w in self._historico_scroll.winfo_children():
            w.destroy()

        try:
            historico = self._servico.historico_bem(self._usuario.id, self._bem_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        if not historico:
            ctk.CTkLabel(self._historico_scroll, text="Sem movimentações registradas.",
                        text_color="#888780", font=ctk.CTkFont(size=11)).pack(pady=12)
            return

        for mov in reversed(historico):
            item = ctk.CTkFrame(self._historico_scroll, fg_color="transparent")
            item.pack(fill="x", pady=4, padx=6)

            tipo_label = _TIPO_MOV_LABEL.get(mov.tipo.value, mov.tipo.value)
            ctk.CTkLabel(item, text=tipo_label, text_color="#3d3d3a",
                         font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")

            partes = []
            if mov.localizacao_origem and mov.localizacao_destino:
                partes.append(f"{mov.localizacao_origem.nome_completo} › {mov.localizacao_destino.nome_completo}")
            elif mov.localizacao_destino:
                partes.append(mov.localizacao_destino.nome_completo)
            data_str = mov.data_hora.strftime("%d/%m/%Y %H:%M")
            usuario_str = mov.usuario.nome if mov.usuario else "—"
            partes.append(f"{data_str} · {usuario_str}")
            if mov.motivo:
                partes.append(mov.motivo)

            ctk.CTkLabel(item, text="\n".join(partes), text_color="#888780",
                         font=ctk.CTkFont(size=10), anchor="w", justify="left").pack(fill="x")
            ctk.CTkFrame(self._historico_scroll, fg_color=COR_CINZA_E, height=1).pack(fill="x", padx=6, pady=(4, 0))

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _confirmar_transferencia(self):
        loc_label = self._opt_destino.get()
        destino = next((loc for loc in self._localizacoes if loc.nome_completo == loc_label), None)
        motivo = self._txt_motivo_transf.get("1.0", "end").strip()

        if not destino:
            self._banner.erro("Selecione uma localização de destino válida.")
            return
        if not motivo:
            self._banner.erro("Motivo é obrigatório.")
            return

        try:
            self._servico.transferir_bem(self._bem_id, destino.id, motivo, usuario_id=self._usuario.id)
            self._banner.sucesso("Bem transferido com sucesso.")
            self._carregar()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao transferir bem: %s", exc)
            self._banner.erro(f"Erro ao transferir: {exc}")

    def _selecionar_anexo_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar anexo da baixa", filetypes=[("PDF", "*.pdf")])
        if not caminho:
            return
        try:
            with open(caminho, "rb") as f:
                self._anexo_bytes = f.read()
            self._anexo_nome = os.path.basename(caminho)
            self._lbl_anexo.configure(text=self._anexo_nome, text_color="#3d3d3a")
        except OSError as exc:
            self._banner.erro(f"Erro ao ler arquivo: {exc}")

    def _confirmar_baixa(self):
        motivo = _MOTIVOS_BAIXA.get(self._opt_motivo_baixa.get())
        data_texto = self._campo_data_baixa.get()

        try:
            data_baixa = datetime.strptime(data_texto, "%d/%m/%Y").date()
        except ValueError:
            self._banner.erro("Data da baixa inválida. Use dd/mm/aaaa.")
            return

        dados = DadosBaixa(
            motivo=motivo,
            data_baixa=data_baixa,
            anexo_conteudo=self._anexo_bytes or b"",
            anexo_nome=self._anexo_nome or "",
            numero_mtr=self._campo_mtr.get() or None,
            numero_laudo=self._campo_laudo.get() or None,
            documento=self._campo_documento.get() or None,
        )

        try:
            self._servico.baixar_bem(self._bem_id, dados, usuario_id=self._usuario.id)
            self._banner.sucesso("Baixa registrada com sucesso.")
            self._carregar()
        except (AnexoObrigatorioError, AnexoInvalidoError, AnexoExcedidoError, PatrimonioError) as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao baixar bem: %s", exc)
            self._banner.erro(f"Erro ao baixar: {exc}")

    def _mostrar_info_baixa(self):
        if self._card_baixa_info:
            self._card_baixa_info.destroy()
            self._card_baixa_info = None

        try:
            baixa = self._servico.obter_baixa(self._usuario.id, self._bem_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        card = ctk.CTkFrame(self._esquerda, fg_color=COR_BRANCO, corner_radius=8,
                            border_width=1, border_color=COR_CINZA_B)
        card.pack(fill="x", pady=(0, 12))

        motivo_label = next((k for k, v in _MOTIVOS_BAIXA.items() if v == baixa.motivo.value), baixa.motivo.value)
        linhas = [
            ("Motivo", motivo_label),
            ("Data da baixa", baixa.data_baixa.strftime("%d/%m/%Y")),
            ("Número MTR", baixa.numero_mtr or "—"),
            ("Número do laudo", baixa.numero_laudo or "—"),
            ("Referência", baixa.documento or "—"),
        ]
        for k, v in linhas:
            linha = ctk.CTkFrame(card, fg_color="transparent")
            linha.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(linha, text=k, text_color="#888780", font=ctk.CTkFont(size=11),
                         width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(linha, text=v, text_color="#3d3d3a", font=ctk.CTkFont(size=11),
                         anchor="w").pack(side="left")

        botoes_doc = ctk.CTkFrame(card, fg_color="transparent")
        botoes_doc.pack(fill="x", padx=16, pady=(8, 16))
        ctk.CTkButton(botoes_doc, text="Visualizar documento", height=30,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      font=ctk.CTkFont(size=11),
                      command=self._visualizar_documento_pdf).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(botoes_doc, text="Baixar (PDF)", height=30,
                      fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                      border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                      font=ctk.CTkFont(size=11),
                      command=self._baixar_documento_pdf).pack(side="left", fill="x", expand=True, padx=(6, 0))

        self._card_baixa_info = card

    def _visualizar_documento_pdf(self):
        # Abre no visualizador padrão do Windows — sem depender de biblioteca
        # nova para renderizar PDF dentro da janela do SCE. Mesmo padrão de
        # arquivo temporário já usado em XlsxBuilder para relatórios.
        try:
            documento = self._servico.obter_documento_baixa(self._usuario.id, self._bem_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        try:
            pasta_tmp = Path(tempfile.gettempdir()) / "SCU-Uronefrologia" / "patrimonio"
            pasta_tmp.mkdir(exist_ok=True, parents=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho_tmp = pasta_tmp / f"baixa_{self._bem.tombo}_{ts}.pdf"
            caminho_tmp.write_bytes(documento.conteudo)
            os.startfile(caminho_tmp)
        except OSError as exc:
            logger.error("Erro ao abrir documento de baixa: %s", exc)
            self._banner.erro(f"Erro ao abrir documento: {exc}")

    def _baixar_documento_pdf(self):
        try:
            documento = self._servico.obter_documento_baixa(self._usuario.id, self._bem_id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        destino = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=documento.nome_original)
        if not destino:
            return
        try:
            with open(destino, "wb") as f:
                f.write(documento.conteudo)
            self._banner.sucesso("Documento salvo com sucesso.")
        except OSError as exc:
            self._banner.erro(f"Erro ao salvar arquivo: {exc}")

    def _abrir_historico_manutencao(self):
        if not self._bem:
            return
        if self._painel_manutencao:
            self._painel_manutencao.destroy()
        self._painel_manutencao = PainelHistoricoManutencao(
            self, servico=self._servico, usuario=self._usuario, bem=self._bem,
            on_fechar=self._fechar_historico_manutencao)
        self._painel_manutencao.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.55, relheight=0.75)

    def _fechar_historico_manutencao(self):
        if self._painel_manutencao:
            self._painel_manutencao.destroy()
            self._painel_manutencao = None
        self._carregar()

    def limpar_memoria(self):
        """Chamado pelo app.py ao sair da tela — fecha painéis flutuantes abertos."""
        if self._painel_manutencao:
            self._painel_manutencao.destroy()
            self._painel_manutencao = None

    def _confirmar_edicao(self):
        if not self._campo_descricao.validar():
            return

        dados = DadosBem(
            descricao=self._campo_descricao.get(),
            localizacao_id=self._bem.localizacao_id,
            marca_modelo=self._campo_marca.get() or None,
            data_aquisicao=self._parse_data(self._campo_data_aq.get()),
            valor_aquisicao=self._parse_valor(self._campo_valor.get()),
            nota_fiscal=self._campo_nf.get() or None,
            observacao=self._txt_observacao.get("1.0", "end").strip() or None,
        )

        try:
            self._servico.editar_bem(self._bem_id, dados, usuario_id=self._usuario.id)
            self._banner.sucesso("Dados atualizados com sucesso.")
            self._carregar()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao editar bem: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")

    @staticmethod
    def _parse_data(texto: str):
        if not texto:
            return None
        try:
            return datetime.strptime(texto, "%d/%m/%Y").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_valor(texto: str):
        if not texto:
            return None
        from decimal import Decimal, InvalidOperation
        try:
            return Decimal(texto.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return None
