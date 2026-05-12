"""
gui.telas.t07c_entrada_danfe.py
Tela T-07c — Entrada assistida por chave de acesso DANFE (RF-04b / AD-12 / ERS v1.6)

Fluxo:
  1. Técnico lê os 44 dígitos da chave de acesso com o leitor de barras HID USB.
  2. DanfeEntryAssistant valida a chave e extrai número da NF automaticamente.
  3. Botão "Consultar no portal SEFAZ" abre o browser externo (webbrowser.open).
     O técnico resolve o CAPTCHA externamente e consulta os dados da nota.
  4. Técnico preenche os campos do lote (produto, num_lote, datas, qtd, valor).
     Campo nota_fiscal já preenchido e bloqueado para edição.
  5. Confirma → registrar_entrada_danfe() persiste lote com chave_acesso.

Decisão AD-12: o SCE NÃO automatiza nem realiza scraping do portal SEFAZ.
"""
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import customtkinter as ctk
from gui.componentes.form_widgets import (
    CampoBarras, CampoNome, BotoesFormulario, SecaoFormulario, FeedbackBanner, Campo
)
from Modulo_02_estoque import EstoqueService, ProdutoRepo, LoteRepo, DanfeEntryAssistant

logger = logging.getLogger(__name__)

COR_AZUL     = "#1F4E79"
COR_AZUL_M   = "#2E75B6"
COR_AZUL_L   = "#D6E4F0"
COR_CINZA_E  = "#F2F1ED"
COR_CINZA_B  = "#E8E6DE"
COR_BRANCO   = "#FFFFFF"
COR_VERDE    = "#EAF3DE"
COR_VERDE_T  = "#27500A"
COR_AMBER_BG = "#FAEEDA"
COR_AMBER_T  = "#854F0B"
COR_VERM     = "#A32D2D"

UNIDADES = ["caixa", "pacote", "unidade", "ampola", "galao", "fardo",
            "litro", "rolo", "kit", "dose"]
CENTROS  = ["deposito", "almoxarifado", "farmacia"]


class TelaEntradaDANFE(ctk.CTkFrame):
    """
    Entrada de produtos via leitura da chave de acesso do DANFE (NF impressa ou PDF).
    """

    def __init__(self, master, usuario, on_navigate, produto_id: int = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._produto_sel = None
        self._dados_chave = None   # dict retornado por DanfeEntryAssistant.processar_chave()
        self._construir()
        if produto_id:
            self._buscar_produto_por_id(produto_id)

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        # Topbar
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Entrada via DANFE — Chave de Acesso",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
        ctk.CTkLabel(topbar, text="Início › Estoque › Entrada DANFE",
                     font=ctk.CTkFont(size=11),
                     text_color="#888780").pack(side="left", padx=4)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=COR_CINZA_E, corner_radius=8,
            border_width=1, border_color=COR_CINZA_B
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=8)

        self._construir_sec_chave()
        self._construir_sec_produto()
        self._construir_sec_lote()
        self._construir_botoes()

        self._sec_produto.pack_forget()
        self._sec_lote.pack_forget()
        self._chave_entry.focus()

    def _construir_sec_chave(self):
        """Seção 1 — leitura da chave de acesso."""
        sec = SecaoFormulario(self._scroll, "1. Ler chave de acesso do DANFE")
        sec.pack(fill="x", pady=(0, 8))

        # Instrução
        ctk.CTkLabel(
            sec,
            text="Posicione o cursor no campo abaixo e leia o código de barras do DANFE "
                 "(44 dígitos). O campo NF será preenchido automaticamente.",
            font=ctk.CTkFont(size=11), text_color="#5F5E5A",
            anchor="w", justify="left", wraplength=700,
        ).pack(fill="x", padx=14, pady=(0, 8))

        frame_chave = ctk.CTkFrame(sec, fg_color="transparent")
        frame_chave.pack(fill="x", padx=14, pady=(0, 6))
        frame_chave.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(frame_chave, text="Chave de acesso (44 dígitos) *",
                           font=ctk.CTkFont(size=11, weight="bold"),
                           text_color="#888780", anchor="w")
        lbl.grid(row=0, column=0, sticky="w", pady=(0, 2))

        entry_frame = ctk.CTkFrame(frame_chave, fg_color="transparent")
        entry_frame.grid(row=1, column=0, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        self._chave_entry = ctk.CTkEntry(
            entry_frame,
            placeholder_text="Leia o código de barras do DANFE...",
            height=36, font=ctk.CTkFont(size=12),
            fg_color=COR_CINZA_E, border_color=COR_CINZA_B,
        )
        self._chave_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._chave_entry.bind("<Return>", lambda e: self._processar_chave())

        ctk.CTkButton(
            entry_frame, text="Validar", width=80, height=36,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=12),
            command=self._processar_chave,
        ).grid(row=0, column=1)

        # Card de retorno da chave (azul claro, oculto por padrão)
        self._card_chave = ctk.CTkFrame(
            sec, fg_color=COR_AZUL_L, corner_radius=6,
            border_width=1, border_color=COR_AZUL_M
        )

        row_chave_info = ctk.CTkFrame(self._card_chave, fg_color="transparent")
        row_chave_info.pack(fill="x", padx=12, pady=8)

        self._lbl_nf_info = ctk.CTkLabel(
            row_chave_info, text="", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AZUL, anchor="w"
        )
        self._lbl_nf_info.pack(side="left")

        self._btn_sefaz = ctk.CTkButton(
            row_chave_info,
            text="🔗  Consultar no portal SEFAZ",
            width=220, height=30,
            fg_color=COR_AZUL, hover_color="#163d5e",
            font=ctk.CTkFont(size=11),
            command=self._abrir_sefaz,
        )
        self._btn_sefaz.pack(side="right")

        ctk.CTkLabel(
            self._card_chave,
            text="Resolva o CAPTCHA no navegador, consulte os dados da nota e "
                 "preencha os campos abaixo no SCE.",
            font=ctk.CTkFont(size=10), text_color="#5F5E5A",
            anchor="w", justify="left",
        ).pack(fill="x", padx=12, pady=(0, 8))

    def _construir_sec_produto(self):
        """Seção 2 — identificar produto."""
        self._sec_produto = SecaoFormulario(self._scroll, "2. Identificar produto")

        frame_id = ctk.CTkFrame(self._sec_produto, fg_color="transparent")
        frame_id.pack(fill="x", padx=14, pady=(0, 6))
        frame_id.grid_columnconfigure((0, 1), weight=1)

        self._ean = CampoBarras(frame_id, on_leitura=self._on_leitura_ean)
        self._ean.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self._nome = CampoNome(frame_id, on_leitura=self._on_leitura_nome)
        self._nome.grid(row=0, column=1, sticky="ew")

        # Card produto encontrado
        self._card_produto = ctk.CTkFrame(
            self._sec_produto, fg_color=COR_VERDE, corner_radius=6,
            border_width=1, border_color="#97C459"
        )
        self._lbl_produto = ctk.CTkLabel(
            self._card_produto, text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), anchor="w", justify="left"
        )
        self._lbl_produto.pack(anchor="w", padx=12, pady=8)

        # Mini-form cadastro rápido inline
        self._frame_cadastro_rapido = ctk.CTkFrame(
            self._sec_produto, fg_color=COR_AMBER_BG, corner_radius=8,
            border_width=1, border_color="#EF9F27"
        )
        ctk.CTkLabel(
            self._frame_cadastro_rapido,
            text="Produto não encontrado — cadastro rápido",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AMBER_T, anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 0))

        self._lbl_ean_rap = ctk.CTkLabel(
            self._frame_cadastro_rapido, text="",
            text_color=COR_AZUL, font=ctk.CTkFont(size=11, weight="bold"), anchor="w"
        )
        self._lbl_ean_rap.pack(fill="x", padx=14, pady=(4, 4))

        grid_rap = ctk.CTkFrame(self._frame_cadastro_rapido, fg_color="transparent")
        grid_rap.pack(fill="x", padx=14, pady=(0, 4))
        grid_rap.grid_columnconfigure((0, 1, 2), weight=1)

        self._rap_nome = Campo(grid_rap, "Nome do produto *", obrigatorio=True)
        self._rap_nome.grid(row=0, column=0, padx=(0, 8), sticky="ew", columnspan=2)
        self._rap_centro = Campo(grid_rap, "Centro *", tipo="select", opcoes=CENTROS, largura=160)
        self._rap_centro.grid(row=0, column=2, sticky="ew")

        grid_rap2 = ctk.CTkFrame(self._frame_cadastro_rapido, fg_color="transparent")
        grid_rap2.pack(fill="x", padx=14, pady=(0, 4))
        grid_rap2.grid_columnconfigure((0, 1, 2), weight=1)

        self._rap_unidade = Campo(grid_rap2, "Unidade *", tipo="select", opcoes=UNIDADES, largura=160)
        self._rap_unidade.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._rap_fornecedor = Campo(grid_rap2, "Fornecedor", placeholder="Opcional")
        self._rap_fornecedor.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        self._rap_marca = Campo(grid_rap2, "Marca", placeholder="Opcional")
        self._rap_marca.grid(row=0, column=2, sticky="ew")

        row_rap_btns = ctk.CTkFrame(self._frame_cadastro_rapido, fg_color="transparent")
        row_rap_btns.pack(anchor="e", padx=14, pady=(4, 12))
        ctk.CTkButton(row_rap_btns, text="Cancelar", width=90, height=28,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                      font=ctk.CTkFont(size=11),
                      command=self._cancelar_cadastro_rapido).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_rap_btns, text="Cadastrar e continuar →", width=180, height=28,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      font=ctk.CTkFont(size=11),
                      command=self._executar_cadastro_rapido).pack(side="left")

    def _construir_sec_lote(self):
        """Seção 3 — dados do lote (preenchimento manual após consulta SEFAZ)."""
        self._sec_lote = SecaoFormulario(self._scroll, "3. Dados do lote (consultar no portal SEFAZ)")

        # Nota fiscal — bloqueada (preenchida automaticamente da chave)
        frame_nf = ctk.CTkFrame(self._sec_lote, fg_color=COR_AZUL_L,
                                corner_radius=6, border_width=1, border_color=COR_AZUL_M)
        frame_nf.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(frame_nf, text="Número da NF (extraído da chave de acesso):",
                     font=ctk.CTkFont(size=11), text_color=COR_AZUL, anchor="w"
                     ).pack(side="left", padx=12, pady=8)
        self._lbl_nf_valor = ctk.CTkLabel(
            frame_nf, text="—", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AZUL, anchor="w"
        )
        self._lbl_nf_valor.pack(side="left", padx=4, pady=8)

        row1 = ctk.CTkFrame(self._sec_lote, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(0, 6))
        row1.grid_columnconfigure((0, 1), weight=1)
        self._num_lote = Campo(row1, "Número do lote *", obrigatorio=True,
                               placeholder="Ex: L2024-0512")
        self._num_lote.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._data_venc = Campo(row1, "Data de vencimento *", obrigatorio=True,
                                placeholder="DD/MM/AAAA")
        self._data_venc.grid(row=0, column=1, sticky="ew")

        row2 = ctk.CTkFrame(self._sec_lote, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(0, 6))
        row2.grid_columnconfigure((0, 1), weight=1)
        self._data_fab = Campo(row2, "Data de fabricação", placeholder="DD/MM/AAAA")
        self._data_fab.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._quantidade = Campo(row2, "Quantidade *", obrigatorio=True,
                                 tipo="number", placeholder="0")
        self._quantidade.grid(row=0, column=1, sticky="ew")
        self._quantidade._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())

        row3 = ctk.CTkFrame(self._sec_lote, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(0, 6))
        row3.grid_columnconfigure((0, 1), weight=1)
        self._valor_unit = Campo(row3, "Valor unitário (R$) *", obrigatorio=True,
                                 tipo="number", placeholder="0,00")
        self._valor_unit.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._valor_unit._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())

        self._lbl_total = ctk.CTkLabel(
            self._sec_lote, text="Valor total: —",
            text_color=COR_AZUL, font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        )
        self._lbl_total.pack(fill="x", padx=14, pady=(0, 10))

    def _construir_botoes(self):
        self._row_btns = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._row_btns.pack(anchor="e", pady=(0, 8))
        self._row_btns.pack_forget()

        ctk.CTkButton(
            self._row_btns, text="Cancelar", width=90, height=34,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
            command=lambda: self._on_navigate("entrada_manual"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self._row_btns, text="Registrar entrada", width=160, height=34,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            command=self._salvar,
        ).pack(side="left")

    # ── Lógica da chave ───────────────────────────────────────────────────────

    def _processar_chave(self):
        chave = self._chave_entry.get().strip()
        if not chave:
            self._banner.erro("Leia ou informe a chave de acesso.")
            return

        dados = DanfeEntryAssistant.processar_chave(chave)
        if not dados["valida"]:
            self._banner.erro(dados["erro"])
            self._card_chave.pack_forget()
            return

        self._dados_chave = dados

        # Exibir card com dados extraídos
        self._lbl_nf_info.configure(
            text=f"  NF nº {dados['numero_nf']}  ·  Série {dados['serie']}  ·"
        )
        self._card_chave.pack(fill="x", padx=14, pady=(0, 8))
        self._lbl_nf_valor.configure(text=dados["numero_nf"])

        # Revelar seções seguintes
        self._sec_produto.pack(fill="x", pady=(0, 8))
        self._sec_lote.pack(fill="x", pady=(0, 8))
        self._row_btns.pack(anchor="e", pady=(0, 8))

        self._banner.limpar()
        self._ean.focus()

    def _abrir_sefaz(self):
        if not self._dados_chave:
            return
        ok = DanfeEntryAssistant.abrir_portal_sefaz(self._dados_chave["chave"])
        if ok:
            self._banner.limpar()
            # Aviso informativo — não bloqueia fluxo
            info = ctk.CTkLabel(
                self._scroll,
                text="🌐  Portal SEFAZ aberto no navegador. Resolva o CAPTCHA, "
                     "consulte os dados e preencha os campos abaixo.",
                font=ctk.CTkFont(size=11), text_color=COR_AZUL,
                fg_color=COR_AZUL_L, corner_radius=6, anchor="w",
            )
            info.pack(fill="x", padx=14, pady=(0, 8))
            self.after(8000, info.destroy)
        else:
            self._banner.erro(
                "Não foi possível abrir o navegador automaticamente. "
                f"Acesse manualmente: https://www.nfe.fazenda.gov.br"
            )

    # ── Produto ───────────────────────────────────────────────────────────────

    def _on_leitura_ean(self, ean: str):
        self._card_produto.pack_forget()
        self._frame_cadastro_rapido.pack_forget()
        self._produto_sel  = None
        self._ean_pendente = None
        if not ean.strip():
            return
        try:
            produto = EstoqueService.buscar_produto_por_ean(ean)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return
        if produto:
            self._mostrar_produto(produto)
        else:
            self._ean_pendente = ean
            self._lbl_ean_rap.configure(text=f"  EAN lido: {ean}")
            self._rap_nome.limpar()
            self._frame_cadastro_rapido.pack(fill="x", padx=14, pady=(0, 8))
            self._rap_nome.focus()

    def _on_leitura_nome(self, nome: str):
        self._card_produto.pack_forget()
        self._produto_sel = None
        if not nome.strip():
            return
        try:
            produto = EstoqueService.buscar_produto_por_nome(nome)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return
        if produto:
            self._mostrar_produto(produto)

    def _mostrar_produto(self, produto):
        self._produto_sel = produto
        centro = produto.centro_alocacao.value if hasattr(produto.centro_alocacao, "value") else str(produto.centro_alocacao)
        self._lbl_produto.configure(
            text=(f"  {produto.nome}\n"
                  f"  Centro: {centro}  ·  "
                  f"Fornecedor: {produto.fornecedor or '—'}  ·  "
                  f"Estoque mín.: {produto.estoque_minimo}")
        )
        self._card_produto.pack(fill="x", padx=14, pady=(0, 8))
        self._banner.limpar()
        self._num_lote.focus()

    def _buscar_produto_por_id(self, id_: int):
        p = ProdutoRepo.buscar_por_id(id_)
        if p:
            self._ean.set(p.ean)
            self._on_leitura_ean(p.ean)

    def _executar_cadastro_rapido(self):
        if not self._rap_nome.validar():
            return
        ean       = self._ean_pendente
        nome      = self._rap_nome.get().strip()
        centro    = self._rap_centro.get()
        unidade   = self._rap_unidade.get()
        fornecedor= self._rap_fornecedor.get().strip() or None
        marca     = self._rap_marca.get().strip() or None
        try:
            produto = EstoqueService.criar_produto(
                nome=nome, ean=ean, centro_alocacao=centro,
                unidade_estoque=unidade, fornecedor=fornecedor, marca=marca,
            )
            self._ean_pendente = None
            self._frame_cadastro_rapido.pack_forget()
            self._mostrar_produto(produto)
            self._banner.sucesso(f"Produto '{nome}' cadastrado. Preencha os dados do lote.")
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro no cadastro rápido DANFE: %s", exc)
            self._banner.erro(f"Erro ao cadastrar: {exc}")

    def _cancelar_cadastro_rapido(self):
        self._frame_cadastro_rapido.pack_forget()
        self._ean_pendente = None
        self._ean.limpar()
        self._ean.focus()

    # ── Cálculo ───────────────────────────────────────────────────────────────

    def _atualizar_total(self):
        try:
            qtd  = int(self._quantidade.get() or "0")
            vunt = Decimal(self._valor_unit.get().replace(",", ".") or "0")
            self._lbl_total.configure(text=f"Valor total calculado: R$ {qtd * vunt:,.2f}")
        except Exception:
            self._lbl_total.configure(text="Valor total: —")

    # ── Salvar ────────────────────────────────────────────────────────────────

    def _salvar(self):
        if not self._dados_chave:
            self._banner.erro("Leia e valide a chave de acesso primeiro.")
            return
        if not self._produto_sel:
            self._banner.erro("Identifique o produto pelo código de barras.")
            return

        valido = all([
            self._num_lote.validar(),
            self._data_venc.validar(),
            self._quantidade.validar(),
            self._valor_unit.validar(),
        ])
        if not valido:
            return

        data_venc = _parse_date(self._data_venc.get())
        if not data_venc:
            self._data_venc.erro("Data inválida. Use DD/MM/AAAA.")
            return

        data_fab = None
        if self._data_fab.get():
            data_fab = _parse_date(self._data_fab.get())
            if not data_fab:
                self._data_fab.erro("Data inválida. Use DD/MM/AAAA.")
                return

        try:
            qtd = int(self._quantidade.get())
            if qtd <= 0:
                raise ValueError()
        except ValueError:
            self._quantidade.erro("Informe um número inteiro positivo.")
            return

        try:
            vunt = Decimal(self._valor_unit.get().replace(",", "."))
            if vunt <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            self._valor_unit.erro("Informe um valor unitário positivo.")
            return

        try:
            EstoqueService.registrar_entrada_danfe(
                produto_id      = self._produto_sel.id,
                num_lote        = self._num_lote.get(),
                nota_fiscal     = self._dados_chave["numero_nf"],
                chave_acesso    = self._dados_chave["chave"],
                data_vencimento = data_venc,
                data_fabricacao = data_fab,
                quantidade      = qtd,
                valor_unitario  = vunt,
                usuario_id      = self._usuario.id,
            )
        except ValueError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao registrar entrada DANFE: %s", exc)
            self._banner.erro(f"Erro ao registrar: {exc}")
            return

        aviso = ""
        try:
            saldo  = LoteRepo.saldo_total_produto(self._produto_sel.id)
            minimo = self._produto_sel.estoque_minimo
            if minimo > 0 and saldo <= minimo:
                aviso = f" · Atenção: saldo ({saldo}) abaixo do mínimo ({minimo})."
        except Exception:
            pass

        self._banner.sucesso(
            f"Entrada DANFE registrada: {qtd} unid. de '{self._produto_sel.nome}' · "
            f"Lote: {self._num_lote.get()} · NF: {self._dados_chave['numero_nf']}.{aviso}"
        )
        self._oferecer_proxima_acao(self._produto_sel.nome)

    def _oferecer_proxima_acao(self, nome_produto: str):
        for w in self._scroll.winfo_children():
            if getattr(w, "_proximo_bar", False):
                w.destroy()

        bar = ctk.CTkFrame(self._scroll, fg_color="#E6F1FB",
                           corner_radius=8, border_width=1, border_color=COR_AZUL_M)
        bar._proximo_bar = True
        bar.pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(
            bar,
            text=f"Entrada de '{nome_produto[:30]}' registrada. O que deseja fazer?",
            font=ctk.CTkFont(size=11), text_color=COR_AZUL, anchor="w",
        ).pack(side="left", padx=14, pady=10)

        ctk.CTkButton(
            bar, text="Nova entrada DANFE", width=160, height=28,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=11),
            command=self._reiniciar,
        ).pack(side="right", padx=8, pady=8)

        ctk.CTkButton(
            bar, text="Ir para Produtos", width=120, height=28,
            fg_color=COR_BRANCO, text_color=COR_AZUL_M,
            border_width=1, border_color=COR_AZUL_M, hover_color="#E6F1FB",
            font=ctk.CTkFont(size=11),
            command=lambda: self._on_navigate("produtos"),
        ).pack(side="right", pady=8)

    def _reiniciar(self):
        self._dados_chave = None
        self._produto_sel = None
        self._chave_entry.delete(0, "end")
        self._card_chave.pack_forget()
        self._sec_produto.pack_forget()
        self._card_produto.pack_forget()
        self._frame_cadastro_rapido.pack_forget()
        self._sec_lote.pack_forget()
        self._row_btns.pack_forget()
        for campo in [self._num_lote, self._data_fab, self._data_venc,
                      self._quantidade, self._valor_unit]:
            campo.limpar()
        self._lbl_total.configure(text="Valor total: —")
        self._banner.limpar()
        for w in self._scroll.winfo_children():
            if getattr(w, "_proximo_bar", False):
                w.destroy()
        self._chave_entry.focus()


# ── Utilitário ────────────────────────────────────────────────────────────────

def _parse_date(texto: str) -> date | None:
    texto = texto.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None
