"""
gui.telas.t05_novo_produto.py
Tela T-05 — Cadastro / edição de produto (UC-02, RF-01).
 
Questão 1 aplicada:
- Fornecedor agora é campo texto livre (CTkComboBox) — sem FK, sem tabela auxiliar.
- ComboBox carrega valores únicos já cadastrados no banco como sugestão.
- Usuário pode selecionar um existente OU digitar qualquer texto novo livremente.
"""
import logging
import customtkinter as ctk
from gui.componentes.form_widgets import (
    Campo, CampoBarras, BotoesFormulario, SecaoFormulario, FeedbackBanner
)
from Modulo_02_estoque import EstoqueService, ProdutoRepo
 
logger = logging.getLogger(__name__)
 
COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
 
UNIDADES = ["caixa","pacote","unidade","ampola","galao","fardo","litro","rolo","kit","dose"]
CENTROS  = ["almoxarifado", "farmacia"]
 
 
class TelaNovoProduto(ctk.CTkFrame):
    """Cadastro e edição de produto — fornecedor como texto livre com autocomplete."""
 
    def __init__(self, master, usuario, on_navigate, produto_id: int = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._produto_id  = produto_id
        self._construir()
        self._carregar_sugestoes_fornecedor()
        if self._produto_id:
            self._preencher_produto(self._produto_id)
 
    # ── Construção ────────────────────────────────────────────────────────────
 
    def _construir(self):
        titulo = "Editar produto" if self._produto_id else "Novo produto"
 
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text=titulo, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
        ctk.CTkLabel(topbar, text="Início › Produtos › " + titulo,
                     font=ctk.CTkFont(size=11),
                     text_color="#888780").pack(side="left", padx=4)
 
        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))
 
        scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=15)
 
        # ── Seção 1: Identificação ────────────────────────────────────────────
        sec1 = SecaoFormulario(scroll, "Identificação")
        sec1.pack(fill="x", pady=(0, 10))
 
        self._nome = Campo(sec1, "Nome do produto", obrigatorio=True, largura=500)
        self._nome.pack(fill="x", padx=14, pady=(0, 8))
 
        self._ean = CampoBarras(sec1, "Código de barras (EAN)", obrigatorio=True,
                                largura=300, on_leitura=self._ao_ler_ean)
        self._ean.pack(fill="x", padx=14, pady=(0, 8))
 
        self._descricao = Campo(sec1, "Descrição", placeholder="Opcional", largura=500)
        self._descricao.pack(fill="x", padx=14, pady=(0, 12))
 
        # ── Seção 2: Classificação ────────────────────────────────────────────
        sec2 = SecaoFormulario(scroll, "Classificação e estoque")
        sec2.pack(fill="x", pady=(0, 10))
 
        grid1 = ctk.CTkFrame(sec2, fg_color="transparent")
        grid1.pack(fill="x", padx=14, pady=(0, 8))
        grid1.grid_columnconfigure((0, 1, 2), weight=1)
 
        self._centro = Campo(grid1, "Centro de alocação *", tipo="select",
                             opcoes=CENTROS, largura=180)
        self._centro.grid(row=0, column=0, padx=(0, 12), sticky="ew")
 
        self._unidade = Campo(grid1, "Unidade de medida *", tipo="select",
                              opcoes=UNIDADES, largura=160)
        self._unidade.grid(row=0, column=1, padx=(0, 12), sticky="ew")
 
        self._estoque_min = Campo(grid1, "Estoque mínimo", tipo="number",
                                  placeholder="0", largura=120, obrigatorio=True)
        self._estoque_min.grid(row=0, column=2, sticky="ew")
 
        grid2 = ctk.CTkFrame(sec2, fg_color="transparent")
        grid2.pack(fill="x", padx=14, pady=(0, 8))
        grid2.grid_columnconfigure((0, 1), weight=1)
 
        self._marca = Campo(grid2, "Marca", placeholder="Texto livre", largura=220)
        self._marca.grid(row=0, column=0, padx=(0, 12), sticky="ew")
 
        # ── Fornecedor: ComboBox editável ─────────────────────────────────────
        frn_frame = ctk.CTkFrame(grid2, fg_color="transparent")
        frn_frame.grid(row=0, column=1, sticky="ew")
 
        ctk.CTkLabel(frn_frame, text="Fornecedor",
                     text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(frn_frame,
                     text="Digite livremente ou selecione um existente",
                     text_color="#AAAAAA",
                     font=ctk.CTkFont(size=9), anchor="w").pack(fill="x")
 
        self._combo_fornecedor = ctk.CTkComboBox(
            frn_frame, values=[""],
            width=280, height=32, corner_radius=6,
            fg_color=COR_CINZA_E, button_color=COR_AZUL_M,
            text_color="#3d3d3a",
        )
        self._combo_fornecedor.pack(fill="x", pady=(4, 0))
        self._combo_fornecedor.set("")
 
        self._ativo_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sec2, text="Produto ativo",
                        variable=self._ativo_var,
                        text_color="#3d3d3a").pack(anchor="w", padx=14, pady=(0, 12))
 
        btns = BotoesFormulario(scroll, texto_salvar="Salvar produto",
                                on_salvar=self._salvar,
                                on_cancelar=lambda: self._on_navigate("produtos"))
        btns.pack(anchor="e", pady=8)
 
    # ── Dados ─────────────────────────────────────────────────────────────────
 
    def _carregar_sugestoes_fornecedor(self):
        """Popula o ComboBox com fornecedores únicos já cadastrados no banco."""
        try:
            sugestoes = EstoqueService.listar_fornecedores_unicos()
            self._combo_fornecedor.configure(values=[""] + sugestoes)
        except Exception as exc:
            logger.warning("Erro ao carregar sugestões de fornecedor: %s", exc)
 
    def _preencher_produto(self, produto_id: int):
        p = ProdutoRepo.buscar_por_id(produto_id)
        if not p:
            self._banner.erro(f"Produto {produto_id} não encontrado.")
            return
        self._nome.set(p.nome)
        self._ean.set(p.ean or "")
        self._descricao.set(p.descricao or "")
        val_centro  = p.centro_alocacao.value if hasattr(p.centro_alocacao,  "value") else str(p.centro_alocacao)
        val_unidade = p.unidade_estoque.value  if hasattr(p.unidade_estoque,  "value") else str(p.unidade_estoque)
        self._centro.set(val_centro)
        self._unidade.set(val_unidade)
        self._estoque_min.set(str(p.estoque_minimo))
        self._marca.set(p.marca or "")
        self._ativo_var.set(p.ativo)
        self._combo_fornecedor.set(p.fornecedor or "")
 
    def _ao_ler_ean(self, ean: str):
        prod = EstoqueService.buscar_produto_por_ean(ean)
        if prod and prod.id != self._produto_id:
            self._ean.erro(f"EAN já cadastrado: {prod.nome}")
        else:
            self._ean.erro("")
 
    # ── Salvar ────────────────────────────────────────────────────────────────
 
    def _salvar(self):
        ok = all([self._nome.validar(), self._ean.validar(), self._estoque_min.validar()])
        if not ok:
            return
 
        try:
            estoque_min = int(self._estoque_min.get() or 0)
            if estoque_min < 0:
                raise ValueError()
        except ValueError:
            self._estoque_min.erro("Informe um número inteiro não negativo.")
            return
 
        fornecedor = self._combo_fornecedor.get().strip() or None
 
        try:
            if self._produto_id:
                EstoqueService.atualizar_produto(
                    self._produto_id,
                    nome            = self._nome.get(),
                    ean             = self._ean.get(),
                    descricao       = self._descricao.get() or None,
                    centro_alocacao = self._centro.get(),
                    unidade_estoque = self._unidade.get(),
                    estoque_minimo  = estoque_min,
                    marca           = self._marca.get() or None,
                    fornecedor      = fornecedor,
                    ativo           = self._ativo_var.get(),
                )
                self._banner.sucesso("Produto atualizado com sucesso.")
            else:
                EstoqueService.criar_produto(
                    nome            = self._nome.get(),
                    ean             = self._ean.get(),
                    descricao       = self._descricao.get() or None,
                    centro_alocacao = self._centro.get(),
                    unidade_estoque = self._unidade.get(),
                    estoque_minimo  = estoque_min,
                    marca           = self._marca.get() or None,
                    fornecedor      = fornecedor,
                )
                self._banner.sucesso("Produto criado com sucesso.")
                self._limpar()
            # Recarrega sugestões caso o fornecedor seja inédito
            self._carregar_sugestoes_fornecedor()
 
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao salvar produto: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")
 
    def _limpar(self):
        self._nome.limpar()
        self._ean.limpar()
        self._descricao.limpar()
        self._marca.limpar()
        self._estoque_min.set("0")
        self._combo_fornecedor.set("")
        self._ativo_var.set(True)
        self._nome.focus()
 