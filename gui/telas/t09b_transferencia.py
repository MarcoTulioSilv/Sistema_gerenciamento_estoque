"""
gui.telas.t09b_transferencia.py
Tela T-09b — Transferência de produtos entre centros de alocação.

Separada de T-09 (retirada): antes, a transferência era um toggle dentro da
tela de retirada ("Transferir para outro centro?"), e usuários esqueciam de
ativá-lo — o produto saía do centro de origem registrado como consumo
comum, sem nunca aparecer no centro de destino, um erro silencioso de
operação. Aqui a transferência é o único propósito da tela: não tem como
"esquecer de ativar" o que não é mais um toggle.

Etapas, na mesma linha do fluxo de T-09:
    Passo 1 → Centro de origem
    Passo 2 → Identificação do produto (EAN ou nome) + seleção manual dos
              lotes e quantidades a transferir
    Passo 3 → Centro de destino
    Passo 4 → Observações + confirmação

produto_id=N        — atalho (pula a etapa de busca).
centro_origem=str   — pré-seleciona o centro de origem.
"""

import logging
from datetime import date

import customtkinter as ctk
from gui.componentes.form_widgets import Campo, CampoBarras, CampoNome, SecaoFormulario, FeedbackBanner

from Modulo_02_estoque import EstoqueService, LoteRepo, ProdutoRepo, PlanoManual, ItemPlanoManual
from Modulo_06_dados import CentroAlocacaoEnum

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM,
)

COR_VERDE_BG = "#E1F5EE"
COR_VERDE_T  = "#0F6E56"

_PLACEHOLDER_DESTINO = "— selecione —"

_CENTROS: dict[str, str] = {
    c.value: c.value.capitalize() for c in CentroAlocacaoEnum
}
_LABEL_CENTRO: dict[str, str] = {v: k for k, v in _CENTROS.items()}


class TelaTransferencia(ctk.CTkFrame):
    """T-09b — transferência multi-lote entre centros de alocação."""

    def __init__(self, master, usuario, on_navigate, produto_id: int | None = None,
                centro_origem: str | None = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._produto_sel = None
        self._plano = None
        self._centro_origem = centro_origem
        self._lotes_ui_rows = []

        self._construir()

        if produto_id:
            self._preencher_produto_por_id(produto_id)

    # ══════════════════════════════════════════════════════════════════════════
    # Construção
    # ══════════════════════════════════════════════════════════════════════════

    def _construir(self):
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=60, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Transferência entre Centros",
                     font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=COR_AZUL).pack( padx=16, pady=10)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        self.scroll.pack(fill="both", expand=True)

        # ── Passo 1: centro de origem ────────────────────────────────────────
        self._sec_centro = SecaoFormulario(self.scroll, titulo="1. Centro de origem")
        self._sec_centro.pack(fill="x", padx=16, pady=(12, 0))

        row_c = ctk.CTkFrame(self._sec_centro, fg_color="transparent")
        row_c.pack(fill="x", padx=14, pady=(4, 12))

        ctk.CTkLabel(row_c, text="Centro de Retirada",
                     font=ctk.CTkFont(size=12), text_color="#3d3d3a").pack(side="left", padx=(0, 12))

        self._opt_centro = ctk.CTkOptionMenu(
            row_c, values=list(_CENTROS.values()),
            width=160, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a",
            command=self._ao_escolher_centro,
        )
        self._opt_centro.pack(side="left")

        if self._centro_origem and self._centro_origem in _CENTROS:
            self._opt_centro.set(_CENTROS[self._centro_origem])

        # ── Passo 2: identificação do produto (oculto até escolha do centro) ──
        self._sec_produto = SecaoFormulario(self.scroll, titulo="2. Identificar produto")

        row_id = ctk.CTkFrame(self._sec_produto, fg_color="transparent")
        row_id.pack(fill="x", padx=14, pady=(4, 8))
        row_id.grid_columnconfigure((0, 1), weight=1)

        self._campo_ean = CampoBarras(row_id, label="Código de barras (EAN)", on_leitura=self._ao_ler_ean)
        self._campo_ean.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        self._campo_nome = CampoNome(row_id, label="Nome do produto", on_leitura=self._ao_ler_nome)
        self._campo_nome.grid(row=0, column=1, padx=(0, 4), sticky="ew")

        self._frame_produto = ctk.CTkFrame(
            self._sec_produto, fg_color=COR_VERDE_BG,
            corner_radius=6, border_width=1, border_color="#97C459")
        self._lbl_produto = ctk.CTkLabel(
            self._frame_produto, text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), justify="left", anchor="w")
        self._lbl_produto.pack(fill="x", padx=12, pady=8)

        # Seleção manual de lotes/quantidades (revelada junto do passo 3)
        self._sec_plano = SecaoFormulario(self.scroll, titulo="Selecione os lotes e as quantidades")
        self._frame_plano = ctk.CTkFrame(self._sec_plano, fg_color=COR_CINZA_E, corner_radius=6)
        self._frame_plano.pack(fill="x", padx=14, pady=(0, 8))

        # ── Passo 3: centro de destino ──────────────────────────────────────
        self._sec_destino = SecaoFormulario(self.scroll, titulo="3. Centro de Destino")
        row_d = ctk.CTkFrame(self._sec_destino, fg_color="transparent")
        row_d.pack(fill="x", padx=14, pady=(4, 12))

        ctk.CTkLabel(row_d, text="Transferir para qual centro:",
                     font=ctk.CTkFont(size=12), text_color="#3d3d3a").pack(side="left", padx=(0, 12))

        self._opt_centro_dest = ctk.CTkOptionMenu(
            row_d, values=[_PLACEHOLDER_DESTINO],
            width=180, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a")
        self._opt_centro_dest.pack(side="left")

        # ── Observações ──────────────────────────────────────────────────────
        self._sec_obs = SecaoFormulario(self.scroll, titulo="Observações")
        self._campo_obs = ctk.CTkEntry(
            self._sec_obs,
            placeholder_text="Ex: Reposição do estoque da enfermaria 2",
            height=34, corner_radius=6)
        self._campo_obs.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkLabel(self._sec_obs,
                     text="Quando preenchido, aparece em todos os registros desta transferência.",
                     text_color="#888780", font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 12))

        # ── Botões ───────────────────────────────────────────────────────────
        self._row_btns = ctk.CTkFrame(self.scroll, fg_color="transparent")

        ctk.CTkButton(
            self._row_btns, text="Cancelar",
            width=100, height=36,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
            command=lambda: self._on_navigate("produtos"),
        ).pack(side="left", padx=(0, 8))

        self._btn_confirmar = ctk.CTkButton(
            self._row_btns, text="Confirmar transferência",
            width=200, height=36,
            fg_color="#1D9E75", hover_color="#0F6E56",
            state="disabled",
            command=self._confirmar)
        self._btn_confirmar.pack(side="left")

        # Estado inicial: passo 2 em diante oculto (a menos que já venha pré-selecionado)
        if self._centro_origem:
            self._mostrar_sec_produto()
        else:
            self._sec_produto.pack_forget()
            self._sec_plano.pack_forget()
            self._sec_destino.pack_forget()
            self._sec_obs.pack_forget()
            self._row_btns.pack_forget()

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 1 — Escolha do centro de origem
    # ══════════════════════════════════════════════════════════════════════════

    def _ao_escolher_centro(self, label: str):
        self._centro_origem = _LABEL_CENTRO.get(label, label.lower())
        self._mostrar_sec_produto()

        # Destino nunca pode ser o mesmo centro da origem
        outros = [_PLACEHOLDER_DESTINO] + [
            lb for val, lb in _CENTROS.items() if val != self._centro_origem
        ]
        self._opt_centro_dest.configure(values=outros)
        self._opt_centro_dest.set(_PLACEHOLDER_DESTINO)

        self._limpar_produto()

    def _mostrar_sec_produto(self):
        self._sec_produto.pack(fill="x", padx=16, pady=(10, 0))
        self._campo_ean.focus()

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 2 — Identificação do produto + seleção de lotes
    # ══════════════════════════════════════════════════════════════════════════

    def _ao_ler_ean(self, ean: str):
        self._buscar_e_exibir(EstoqueService.buscar_produto_por_ean, ean,
                              erro_msg=f"EAN '{ean}' não cadastrado.")

    def _ao_ler_nome(self, nome: str):
        self._buscar_e_exibir(EstoqueService.buscar_produto_por_nome, nome,
                              erro_msg=f"Produto '{nome}' não encontrado.")

    def _buscar_e_exibir(self, func_busca, valor: str, erro_msg: str):
        if not self._centro_origem:
            self._banner.erro("Selecione o centro de origem antes de buscar o produto.")
            return
        try:
            produto = func_busca(valor)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return

        if produto is None:
            self._banner.erro(erro_msg)
            self._frame_produto.pack_forget()
            self._produto_sel = None
            return

        hoje = date.today()
        try:
            lotes = LoteRepo.listar_por_produto(produto.id)
        except Exception as exc:
            logger.error("Erro ao buscar lotes do produto %s: %s", produto.id, exc)
            self._banner.erro(f"Erro ao buscar lotes: {exc}")
            return

        lotes_vis = [l for l in lotes
                     if l.quantidade_atual > 0
                     and (l.data_vencimento is None or l.data_vencimento >= hoje)
                     and l.centro_alocacao.value == self._centro_origem]

        saldo = sum(l.quantidade_atual for l in lotes_vis)
        n_lotes = len(lotes_vis)
        unidades = list({l.unidade_estoque.value for l in lotes_vis})
        unid_txt = " / ".join(u.capitalize() for u in unidades) or "—"

        self._produto_sel = produto
        self._lbl_produto.configure(
            text=(
                f"{produto.nome}\n"
                f"Saldo em '{(_CENTROS.get(self._centro_origem or '', '—'))}': "
                f"{saldo} unid. em {n_lotes} lote(s)  ·  Unidade: {unid_txt}"
            )
        )
        self._frame_produto.pack(fill="x", padx=14, pady=(0, 8))
        self._listar_lotes_para_selecao_manual(lotes_vis)

    def _preencher_produto_por_id(self, produto_id: int):
        try:
            p = ProdutoRepo.buscar_por_id(produto_id)
            if p:
                self._campo_ean.set(p.ean)
                self._campo_nome.set(p.nome)
                self._ao_ler_ean(str(p.ean))
        except Exception as exc:
            logger.error("Erro ao pré-selecionar produto: %s", exc)

    def _listar_lotes_para_selecao_manual(self, lotes_disponiveis):
        """Renderiza tuplas com Checkbox e Campo de Qtd (desativado por padrão)."""
        for w in self._frame_plano.winfo_children():
            w.destroy()
        self._lotes_ui_rows.clear()

        if not lotes_disponiveis:
            ctk.CTkLabel(self._frame_plano, text="Nenhum lote com saldo disponível neste centro.",
                        text_color="#888780", font=ctk.CTkFont(size=12)).pack(pady=16)
            self._btn_confirmar.configure(state="disabled")
            self._sec_plano.pack(fill="x", padx=16, pady=(10, 0))
            self._sec_destino.pack_forget()
            self._sec_obs.pack_forget()
            self._row_btns.pack_forget()
            return

        ctk.CTkLabel(self._frame_plano, text="Marque os lotes que deseja transferir e informe a quantidade:",
                    font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_AZUL,
                    anchor="w").pack(fill="x", padx=10, pady=(8, 6))

        for lote in lotes_disponiveis:
            linha = ctk.CTkFrame(self._frame_plano, fg_color=COR_BRANCO, corner_radius=6,
                                 border_width=1, border_color=COR_CINZA_B, cursor="hand2")
            linha.pack(fill="x", padx=10, pady=3)

            var_check = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(linha, text="", variable=var_check, width=24,
                                  fg_color=COR_AZUL_M, hover_color="#1a5276")
            chk.grid(row=0, column=0, padx=(10, 0), pady=10, sticky="w")

            venc_str = lote.data_vencimento.strftime('%d/%m/%Y') if lote.data_vencimento else "Uso Contínuo"
            dados = [
                (f"Lote: {lote.num_lote or 'S/L'}", 100, COR_AZUL, True),
                (f"Validade: {venc_str}", 150, "#4B4A47", True),
                (f"Saldo Atual: {lote.quantidade_atual}", 120, "#3d3d3a", False),
            ]

            acao_clique = lambda e, c=chk: c.toggle()
            linha.bind("<Button-1>", acao_clique)

            for col, (txt, w, cor, bold) in enumerate(dados, start=1):
                lbl = ctk.CTkLabel(linha, text=txt, width=w, anchor="w",
                                   font=ctk.CTkFont(size=11, weight="bold" if bold else "normal"), text_color=cor)
                lbl.grid(row=0, column=col, padx=6, pady=10, sticky="w")
                lbl.bind("<Button-1>", acao_clique)

            lbl_qtd = ctk.CTkLabel(linha, text="Quantidade a transferir:",
                                   font=ctk.CTkFont(size=11, weight="bold"), text_color="#3d3d3a")
            lbl_qtd.grid(row=0, column=4, padx=(10, 2), pady=10, sticky="e")
            lbl_qtd.bind("<Button-1>", acao_clique)

            entry_qtd = ctk.CTkEntry(linha, width=70, height=28, corner_radius=6,
                                     justify="center", state="disabled", fg_color=COR_CINZA_E)
            entry_qtd.grid(row=0, column=5, padx=(0, 10), pady=8, sticky="w")

            chk.configure(command=lambda c=var_check, e=entry_qtd: self._ao_alternar_check_lote(c, e))
            self._lotes_ui_rows.append({"lote": lote, "var_check": var_check, "entry_qtd": entry_qtd})

        self._sec_plano.pack(fill="x", padx=16, pady=(10, 0))
        self._sec_destino.pack(fill="x", padx=16, pady=(10, 0))
        self._sec_obs.pack(fill="x", padx=16, pady=(6, 0))
        self._btn_confirmar.configure(state="normal")
        self._row_btns.pack(anchor="e", padx=16, pady=(0, 16))
        self._resetar_scroll()

    def _ao_alternar_check_lote(self, var_check, entry_widget):
        if var_check.get():
            entry_widget.configure(state="normal", fg_color=COR_BRANCO, border_color=COR_AZUL_M)
            entry_widget.focus()
        else:
            entry_widget.delete(0, "end")
            entry_widget.configure(state="disabled", fg_color=COR_CINZA_E, border_color=COR_CINZA_B)

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 3 + confirmação
    # ══════════════════════════════════════════════════════════════════════════

    def _confirmar(self):
        obs = self._campo_obs.get().strip() or None

        itens_manuais = []
        for item_ui in self._lotes_ui_rows:
            if item_ui["var_check"].get():
                lote = item_ui["lote"]
                try:
                    qtd_digitada = int(item_ui["entry_qtd"].get())
                    if qtd_digitada <= 0:
                        raise ValueError()
                    if qtd_digitada > lote.quantidade_atual:
                        raise ValueError()
                except ValueError:
                    self._banner.erro(
                        f"Erro no lote {lote.num_lote or 'S/L'}: número inválido ou maior que o saldo atual.",
                        15000)
                    return
                itens_manuais.append(ItemPlanoManual(
                    lote.id, lote.num_lote, qtd_digitada, lote.quantidade_atual, lote.unidade_estoque.value))

        if not itens_manuais:
            self._banner.erro("Selecione ao menos um lote para continuar.")
            return

        centro_dest_lb = self._opt_centro_dest.get()
        if centro_dest_lb == _PLACEHOLDER_DESTINO:
            self._banner.erro("Selecione o centro de destino.")
            return
        destino_centro = _LABEL_CENTRO.get(centro_dest_lb, centro_dest_lb.lower())

        self._plano = PlanoManual(self._produto_sel.id, itens_manuais)

        try:
            EstoqueService.registrar_transferencia(
                self._plano, self._usuario.id,
                destino_centro=destino_centro,
                observacao=obs,
            )
            unid_o = self._plano.unidade_estoque.capitalize()
            msg = (f"Transferência: {self._plano.quantidade_pedida} {unid_o} "
                   f"de '{_CENTROS.get(self._centro_origem, self._centro_origem)}' "
                   f"para '{centro_dest_lb}'.")
            self._banner.sucesso(msg)
            self._limpar()
        except ValueError as exc:
            logger.error("Erro na transferência: %s", exc)
            self._banner.erro(str(exc), 15000)
        except Exception as exc:
            logger.error("Erro na transferência: %s", exc)
            self._banner.erro(f"Erro ao registrar: {exc}", 15000)

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _limpar_produto(self):
        self._produto_sel = None
        self._plano = None
        self._campo_ean.limpar()
        self._campo_nome.limpar()
        self._frame_produto.pack_forget()
        self._limpar_plano()
        self._resetar_scroll()

    def _limpar_plano(self):
        self._sec_plano.pack_forget()
        self._sec_destino.pack_forget()
        self._sec_obs.pack_forget()
        self._row_btns.pack_forget()
        self._btn_confirmar.configure(state="disabled")

    def _limpar(self):
        """Reset completo para nova transferência."""
        self._limpar_produto()
        self._campo_obs.delete(0, "end")
        if not self._centro_origem:
            self._sec_produto.pack_forget()
            self._opt_centro.set(list(_CENTROS.values())[0])
            self._centro_origem = None
            self._resetar_scroll()

    def limpar_memoria(self):
        if hasattr(self, "_produto_sel"):
            self._produto_sel = None
        if hasattr(self, "_plano"):
            self._plano = None

    def _resetar_scroll(self):
        self.update_idletasks()
        if hasattr(self, "scroll") and hasattr(self.scroll, "_parent_canvas"):
            self.scroll._parent_canvas.yview_moveto(0.0)
