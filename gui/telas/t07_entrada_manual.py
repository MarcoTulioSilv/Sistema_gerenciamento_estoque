"""
gui.telas.t07_entrada_manual.py
Tela T-07 — Registro de entrada manual (UC-03, UC-04, RF-02, RF-03, RN-07).
 
Questão 2 aplicada:
- EAN não encontrado: expande mini-formulário inline para cadastro rápido do produto
  (nome, — fornecedor e marca opcionais) sem sair da tela.
- Após cadastro rápido, prossegue diretamente para o formulário do lote.
- Modo "lote em lote": após registrar uma entrada, oferece "Próximo lote deste produto"
  e "Próximo produto" para agilizar NFs físicas com vários itens.
"""
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
 
import customtkinter as ctk
from gui.componentes.form_widgets import (
    CampoNome, CampoBarras, BotoesFormulario, SecaoFormulario, FeedbackBanner, Campo
)
from Modulo_02_estoque import EstoqueService, ProdutoRepo, LoteRepo
from gui.telas.t07c_entrada_danfe import TelaEntradaDANFE
 
logger = logging.getLogger(__name__)
 
COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_BRANCO  = "#FFFFFF"
COR_VERDE   = "#EAF3DE"
COR_VERDE_T = "#27500A"
COR_AMBER_BG= "#FAEEDA"
COR_AMBER_T = "#854F0B"
COR_VERM    = "#A32D2D"
 
UNIDADES = ["caixa","pacote","unidade","ampola","galao","fardo","litro","rolo","kit","dose"]
CENTROS  = ["deposito","almoxarifado", "farmacia"]
 
 
class TelaEntradaManual(ctk.CTkFrame):
    """Entrada manual com cadastro rápido inline e modo lote em lote."""
 
    def __init__(self, master, usuario, on_navigate, produto_id: int = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario      = usuario
        self._on_navigate  = on_navigate
        self._produto_sel  = None   # Produto selecionado
        self._ean_pendente = None   # EAN lido mas produto não cadastrado
        self._construir()
        if produto_id:
            self._buscar_produto_por_id(produto_id)
 
    # ── Construção ────────────────────────────────────────────────────────────
 
    def _construir(self):
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text="Entrada manual de produto",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
        ctk.CTkLabel(self._topbar, text="Início › Estoque › Entrada manual",
                     font=ctk.CTkFont(size=11),
                     text_color="#888780").pack(side="left", padx=4)
 
        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)
        
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=8, border_width=1, border_color=COR_CINZA_B)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=1)
 
        # ── Seção 1: Identificar produto ──────────────────────────────────────
        self._sec1 = SecaoFormulario(self._scroll, "1. Identificar produto")
        self._sec1.pack(fill="x", pady=(0, 8))
 
        frame_identificacao = ctk.CTkFrame(self._sec1, fg_color="transparent")
        frame_identificacao.pack(fill="x", padx=14, pady=(0, 6))

        frame_identificacao.grid_columnconfigure((0, 1), weight=1)

        self._ean = CampoBarras(frame_identificacao, on_leitura=self._on_leitura_ean)
        self._ean.grid(row=0,column=0,padx=(0,8), sticky="ew")

        self._nome = CampoNome(frame_identificacao, on_leitura=self._on_leitura_nome)
        self._nome.grid(row=0,column=1, sticky="ew")
 
        # Card: produto encontrado (verde)
        self._card_produto = ctk.CTkFrame(
            self._sec1, fg_color=COR_VERDE, corner_radius=6,
            border_width=1, border_color="#97C459")
        self._lbl_produto = ctk.CTkLabel(
            self._card_produto, text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), anchor="w", justify="left")
        self._lbl_produto.pack(anchor="w", padx=12, pady=8)
 
        # ── Mini-form: cadastro rápido inline (âmbar, oculto por padrão) ──────
        self._frame_cadastro_rapido = ctk.CTkFrame(
            self._sec1, fg_color=COR_AMBER_BG, corner_radius=8,
            border_width=1, border_color="#EF9F27")
 
        ctk.CTkLabel(
            self._frame_cadastro_rapido,
            text="Produto não encontrado — cadastro rápido",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AMBER_T, anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 0))
 
        ctk.CTkLabel(
            self._frame_cadastro_rapido,
            text="Preencha os campos abaixo para cadastrar e continuar "
                 "a entrada sem sair da tela.",
            font=ctk.CTkFont(size=10), text_color="#5F5E5A",
            anchor="w", justify="left",
        ).pack(fill="x", padx=14, pady=(2, 8))
 
        # EAN pré-preenchido (somente leitura no mini-form)
        self._lbl_ean_rap = ctk.CTkLabel(
            self._frame_cadastro_rapido,
            text="", text_color=COR_AZUL,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
        self._lbl_ean_rap.pack(fill="x", padx=14, pady=(0, 6))
 
        grid_rap = ctk.CTkFrame(self._frame_cadastro_rapido, fg_color="transparent")
        grid_rap.pack(fill="x", padx=14, pady=(0, 8))
        grid_rap.grid_columnconfigure((0, 1, 2), weight=1)
 
        self._rap_nome = Campo(grid_rap, "Nome do produto *", obrigatorio=True)
        self._rap_nome.grid(row=0, column=0, padx=(0, 8), sticky="ew", columnspan=2)

 
        grid_rap2 = ctk.CTkFrame(self._frame_cadastro_rapido, fg_color="transparent")
        grid_rap2.pack(fill="x", padx=14, pady=(0, 4))
        grid_rap2.grid_columnconfigure((0, 1, 2), weight=1)
 
 
        self._rap_fornecedor = Campo(grid_rap2, "Fornecedor", placeholder="Opcional")
        self._rap_fornecedor.grid(row=0, column=1, padx=(0, 8), sticky="ew")
 
        self._rap_marca = Campo(grid_rap2, "Marca", placeholder="Opcional")
        self._rap_marca.grid(row=0, column=2, sticky="ew")
 
        row_rap_btns = ctk.CTkFrame(self._frame_cadastro_rapido, fg_color="transparent")
        row_rap_btns.pack(anchor="e", padx=14, pady=(4, 12))
        ctk.CTkButton(
            row_rap_btns, text="Cancelar", width=90, height=28,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
            font=ctk.CTkFont(size=11),
            command=self._cancelar_cadastro_rapido,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row_rap_btns, text="Cadastrar e continuar ->", width=180, height=28,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=11),
            command=self._executar_cadastro_rapido,
        ).pack(side="left")
 
        # ── Seção 2: Dados do lote ────────────────────────────────────────────
        self._sec2 = SecaoFormulario(self._scroll, "2. Dados do lote")
        self._sec2.pack(fill="x", pady=(0, 8))
 
        row1 = ctk.CTkFrame(self._sec2, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(0, 6))
        row1.grid_columnconfigure((0, 1), weight=1)
        self._num_lote = Campo(row1, "Número do lote *", obrigatorio=True,
                               placeholder="Ex: L2024-0512")
        self._num_lote.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._nota_fiscal = Campo(row1, "Nota fiscal (NF)", obrigatorio=True,
                                  placeholder="Número da NF física")
        self._nota_fiscal.grid(row=0, column=1, sticky="ew")
        
        
        row2 = ctk.CTkFrame(self._sec2, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(0, 6))
        row2.grid_columnconfigure((0, 1, 2), weight=1)
        #campo centro de alocação
        self._centro = Campo(row2, "Centro de alocação *", tipo="select",
                                 opcoes=CENTROS, largura=160)
        self._centro.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        #campo unidade
        self._unidade = Campo(row2, "Unidade *", tipo="select",
                                  opcoes=UNIDADES, largura=160)
        self._unidade.grid(row=0, column=1, sticky="e")

        #check box para validade
        self._rap_controla_val= ctk.CTkCheckBox(
            row2, text="Possui validade/lote?",
            text_color= COR_AZUL, font= ctk.CTkFont(size=11, weight="bold")
        )
        self._rap_controla_val.grid(row=0, column=2, sticky="e", padx=(0,8) )
        self._rap_controla_val.select()
 
        row3 = ctk.CTkFrame(self._sec2, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(0, 6))
        row3.grid_columnconfigure((0, 1), weight=1)
        self._data_fab = Campo(row3, "Data de fabricação", placeholder="DD/MM/AAAA")
        self._data_fab.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._data_venc = Campo(row3, "Data de vencimento *", obrigatorio=True,
                                placeholder="DD/MM/AAAA")
        self._data_venc.grid(row=0, column=1, sticky="ew")
 
        row4 = ctk.CTkFrame(self._sec2, fg_color="transparent")
        row4.pack(fill="x", padx=14, pady=(0, 6))
        row4.grid_columnconfigure((0, 1), weight=1)
        self._quantidade = Campo(row4, "Quantidade *", obrigatorio=True,
                                 tipo="number", placeholder="0")
        self._quantidade.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._quantidade._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())
        self._valor_unit = Campo(row4, "Valor unitário (R$) *", obrigatorio=True,
                                 tipo="number", placeholder="0,00")
        self._valor_unit.grid(row=0, column=1, sticky="ew")
        self._valor_unit._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())
 
        self._lbl_total = ctk.CTkLabel(
            self._sec2, text="Valor total: —",
            text_color=COR_AZUL, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        self._lbl_total.pack(fill="x", padx=14, pady=(0, 10))
 
        # ── Botões principais ─────────────────────────────────────────────────
        self._row_btns = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._row_btns.pack(anchor="e", pady=(0, 8))
 
        ctk.CTkButton(
            self._row_btns, text="Cancelar", width=90, height=34,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
            command=lambda: self._on_navigate("produtos"),
        ).pack(side="left", padx=(0, 8))
 
        ctk.CTkButton(
            self._row_btns, text="Registrar entrada", width=160, height=34,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            command=self._salvar,
        ).pack(side="left")
 
        self._ean.focus()
 
    # ── Leitura EAN ───────────────────────────────────────────────────────────
 
    def _on_leitura_ean(self, ean: str):
        """Chamado ao pressionar Enter no campo EAN."""
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
            # Produto encontrado — exibe card verde
            self._produto_sel = produto
            self._lbl_produto.configure(
                text=(f"  {produto.nome}\n"
                      f"  ·  Fornecedor: {produto.fornecedor or '—'}"
                      f"  ·  Estoque mín.: {produto.estoque_minimo}")
            )
            self._card_produto.pack(fill="x", padx=14, pady=(0, 8))
            self._banner._limpar()
        else:
            # Produto não encontrado — abre mini-form inline
            self._ean_pendente = ean
            self._lbl_ean_rap.configure(text=f"  EAN lido: {ean}")
            self._rap_nome.limpar()
            self._rap_fornecedor.limpar()
            self._rap_marca.limpar()
            self._frame_cadastro_rapido.pack(fill="x", padx=14, pady=(0, 8))
            self._rap_nome.focus()
 
    def _on_leitura_nome(self, nome: str):
        """Chamado ao pressionar Enter no campo NOME."""
        self._card_produto.pack_forget()
        self._frame_cadastro_rapido.pack_forget()
        self._produto_sel  = None
        self._nome_pendente = None
 
        if not nome.strip():
            return
 
        try:
            produto = EstoqueService.buscar_produto_por_nome(nome)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return
 
        if produto:
            # Produto encontrado — exibe card verde
            self._produto_sel = produto
            self._lbl_produto.configure(
                text=(f"  {produto.nome}\n"
                      f"  ·  Fornecedor: {produto.fornecedor or '—'}"
                      f"  ·  Estoque mín.: {produto.estoque_minimo}")
            )
            self._card_produto.pack(fill="x", padx=14, pady=(0, 8))
            self._banner._limpar()

    def _buscar_produto_por_id(self, id_: int):
        p = ProdutoRepo.buscar_por_id(id_)
        if p:
            self._ean.set(p.ean)
            self._on_leitura_ean(p.ean)

    def _mostrar_produto(self, produto):
        """Prepara o card verde e desabilita os campos se for item de consumo."""
        self._produto_sel = produto
        controla_val = getattr(produto, 'controla_validade', True)
        status_val = "Sim" if controla_val else "Não (Uso Contínuo)"
        
        self._lbl_produto.configure(
            text=(f"  {produto.nome}\n"
                  f"  ·  Fornecedor: {produto.fornecedor or '—'}  ·  "
                  f"Estoque mín.: {produto.estoque_minimo}  ·  Rastreabilidade: {status_val}")
        )
        self._card_produto.pack(fill="x", padx=14, pady=(0, 8))
        self._banner._limpar()
        
        
        if not controla_val:
            self._num_lote.limpar()
            self._data_venc.limpar()
            self._data_fab.limpar()
            
            for widget in [self._num_lote, self._data_venc, self._data_fab]:
                widget._widget.configure(state="disabled", fg_color=COR_CINZA_B)
                
            self._quantidade.focus() 
        else:
            for widget in [self._num_lote, self._data_venc, self._data_fab]:
                widget._widget.configure(state="normal", fg_color=COR_CINZA_E)
                
            if not self._num_lote.get():
                self._num_lote.focus()
    

 
    # ── Cadastro rápido ───────────────────────────────────────────────────────
 
    def _executar_cadastro_rapido(self):
        """Cadastra produto com dados mínimos e continua para o formulário do lote."""
        if not self._rap_nome.validar():
            return
 
        ean       = self._ean_pendente
        nome      = self._rap_nome.get().strip()
        fornecedor= self._rap_fornecedor.get().strip() or None
        marca     = self._rap_marca.get().strip() or None
 
        try:
            produto = EstoqueService.criar_produto(
                nome            = nome,
                ean             = ean,
                estoque_minimo  = 0,
                fornecedor      = fornecedor,
                marca           = marca,
                controla_validade= bool(self._rap_controla_val.get())
            )
            self._produto_sel  = produto
            self._ean_pendente = None
            logger.info("Produto criado via cadastro rápido em T-07: %s [%s]", nome, ean)
 
        except ValueError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro no cadastro rápido: %s", exc)
            self._banner.erro(f"Erro ao cadastrar produto: {exc}")
            return
 
        # Fecha mini-form e mostra card verde com produto recém-criado
        self._frame_cadastro_rapido.pack_forget()
        self._lbl_produto.configure(
            text=(f"  {produto.nome}  ·  "
                  f"Cadastrado agora — preencha os dados do lote abaixo.")
        )
        self._card_produto.pack(fill="x", padx=14, pady=(0, 8))
        self._banner.sucesso(
            f"Produto '{nome}' cadastrado. Preencha os dados do lote para registrar a entrada.")
        self._num_lote.focus()
 
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
            total = qtd * vunt
            self._lbl_total.configure(text=f"Valor total calculado: R$ {total:,.2f}")
        except Exception:
            self._lbl_total.configure(text="Valor total: —")
 
    # ── Salvar ────────────────────────────────────────────────────────────────
 
    def _salvar(self):
        if not self._produto_sel:
            self._banner.erro("Identifique o produto pelo código de barras antes de registrar.")
            return
        controla_val= getattr(self._produto_sel, 'controla_validade', True)

        campos_gerais=[self._quantidade.validar(), self._valor_unit.validar()]
        if controla_val:
            if not all(campos_gerais+ [self._num_lote.validar(), self._data_venc.validar()]):
                return
        else:
            if not all(campos_gerais):
                return
 
        data_venc=None
        data_fab= None

        num_lote_final= ""

        if controla_val:
            data_venc = _parse_date(self._data_venc.get())
            if not data_venc:
                self._data_venc.erro("Data inválida. Use DD/MM/AAAA.")
                return
            num_lote_final=self._num_lote.get()
 
        
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

        nf_segura= self._nota_fiscal.get().strip() if self._nota_fiscal.get() else ""
        centro_seguro = self._centro.get().strip() if self._centro.get() else ""
        unidade_segura = self._unidade.get().strip() if self._unidade.get() else ""
        try:
            EstoqueService.registrar_entrada_manual(
                produto_id              = self._produto_sel.id,
                num_lote                = num_lote_final,
                nota_fiscal             = self._nota_fiscal.get() or None,
                data_vencimento         = data_venc,
                data_fabricacao         = data_fab,
                quantidade              = qtd,
                valor_unitario          = vunt,
                usuario_id              = self._usuario.id,
                centro_alocacao         = self._centro.get(),
                unidade_estoque         = self._unidade.get()
            )
        except ValueError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao registrar entrada: %s", exc)
            self._banner.erro(f"Erro ao registrar: {exc}")
            return
 
        # Verificar estoque mínimo pós-entrada
        aviso = ""
        try:
            saldo  = LoteRepo.saldo_total_produto(self._produto_sel.id)
            minimo = self._produto_sel.estoque_minimo
            if minimo > 0 and saldo <= minimo:
                aviso = f" · Atenção: saldo ({saldo}) ainda abaixo do mínimo ({minimo})."
        except Exception:
            pass
        
        lote_msg= f"Lote:{num_lote_final}" if controla_val else "Item de Consumo"
        nome_prod = self._produto_sel.nome
        nf        = self._nota_fiscal.get()
        nf_text   = f".NF{nf}" if nf else""
        self._banner.sucesso(
            f"Entrada registrada: {qtd} unid. de '{nome_prod}' · "
            f"Lote: {lote_msg} · NF: {nf_text}.{aviso}"
        )
 
        # ── Modo lote em lote: oferecer próxima ação ──────────────────────────
        self._oferecer_proxima_acao(nome_prod)
 
    def _oferecer_proxima_acao(self, nome_produto: str):
        """Exibe botões para registrar o próximo lote sem reiniciar todo o fluxo."""
        # Remove botões anteriores se existirem
        for w in self._scroll.winfo_children():
            if getattr(w, "_proximo_lote_bar", False):
                w.destroy()
 
        bar = ctk.CTkFrame(self._scroll, fg_color="#E6F1FB",
                           corner_radius=8, border_width=1, border_color=COR_AZUL_M)
        bar._proximo_lote_bar = True
        bar.pack(fill="x", pady=(8, 0))
 
        ctk.CTkLabel(
            bar,
            text=f"Entrada de '{nome_produto[:30]}' registrada. O que deseja fazer?",
            font=ctk.CTkFont(size=11), text_color=COR_AZUL, anchor="w",
        ).pack(side="left", padx=14, pady=10)
 
        ctk.CTkButton(
            bar, text="Próximo lote deste produto", width=190, height=28,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=11),
            command=lambda: self._proximo_lote(manter_produto=True),
        ).pack(side="right", padx=8, pady=8)
 
        ctk.CTkButton(
            bar, text="Próximo produto", width=130, height=28,
            fg_color=COR_BRANCO, text_color=COR_AZUL_M,
            border_width=1, border_color=COR_AZUL_M,
            hover_color="#E6F1FB", font=ctk.CTkFont(size=11),
            command=lambda: self._proximo_lote(manter_produto=False),
        ).pack(side="right", pady=8)
 
    def _proximo_lote(self, manter_produto: bool):
        """Limpa apenas o formulário do lote, mantendo ou não o produto selecionado."""
        produto_anterior = self._produto_sel if manter_produto else None
 
        # Limpa campos do lote
        for campo in [self._num_lote, self._nota_fiscal,
                      self._data_fab, self._data_venc,
                      self._quantidade, self._valor_unit]:
            campo.limpar()
        self._lbl_total.configure(text="Valor total: —")
        self._banner.limpar()
 
        # Remove barra de próxima ação
        for w in self._scroll.winfo_children():
            if getattr(w, "_proximo_lote_bar", False):
                w.destroy()
 
        if manter_produto and produto_anterior:
            # Mantém o produto selecionado — foca direto no lote
            self._produto_sel = produto_anterior
            self._num_lote.focus()
        else:
            # Reinicia a busca de produto
            self._produto_sel = None
            self._card_produto.pack_forget()
            self._ean.limpar()
            
            for widget in[self._num_lote, self._data_venc, self._data_fab]:
                widget._widget.configure(state= "normal", fg_color= COR_CINZA_E)
            
            self._ean.focus()
 
    def _limpar(self):
        self._produto_sel  = None
        self._ean_pendente = None
        self._ean.limpar()
        self._card_produto.pack_forget()
        self._frame_cadastro_rapido.pack_forget()
        for campo in [self._num_lote, self._nota_fiscal, self._data_fab,
                      self._data_venc, self._quantidade, self._valor_unit]:
            campo.limpar()
        self._lbl_total.configure(text="Valor total: —")
        self._ean.focus()
    
    def limpar_memoria(self):
        """Solta a referência ao objeto SQLAlchemy do produto."""
        if hasattr(self, '_produto_sel'):
            self._produto_sel = None
        if hasattr(self, '_ean_pendente'):
            self._ean_pendente = None
 
 
# ── Utilitário ────────────────────────────────────────────────────────────────
 
def _parse_date(texto: str) -> date | None:
    if not texto:
        return None
    
    texto = texto.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None