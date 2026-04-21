"""
gui.telas.t06_novo_fornecedor.py
Tela T-06 — Cadastro / edição de fornecedor (RF-23).
"""
import logging
import customtkinter as ctk
from gui.componentes.form_widgets import Campo, BotoesFormulario, FeedbackBanner
from Modulo_02_estoque import FornecedorRepo
from Modulo_02_estoque import EstoqueService

logger = logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"

class TelaNovoFornecedor(ctk.CTkFrame):

    def __init__(self, master, usuario, on_navigate, fornecedor_id: int = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario      = usuario
        self._on_navigate  = on_navigate
        self._fornecedor_id = fornecedor_id
        self._construir()
        if fornecedor_id:
            self._preencher(fornecedor_id)
    
    def _construir(self):
        titulo= "Editar fornecedor" if self._fornecedor_id else "Novo fornecedor"

        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text=titulo,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8,0))

        card = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=8,
                                border_width=1, border_color=COR_CINZA_B)
        card.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(card, text="Dados do fornecedor",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w", padx=14, pady=(12,0))
        ctk.CTkFrame(card, fg_color=COR_CINZA_B, height=1).pack(fill="x", padx=14, pady=(6,10))

        self._nome = Campo(card, "Nome do fornecedor", obrigatorio=True,
                            placeholder="Nome do fornecedor", largura=480)
        self._nome.pack(fill="x", padx=14, pady=(0,6))
        ctk.CTkLabel(card, text="O fornecedor poderá ser vinculado a um ou mais produtos após o cadastro.",
                     text_color="#888780", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=14, pady=(0,12))
        
        btns = BotoesFormulario(card, texto_salvar="Salvar fornecedor",
                                on_salvar=self._salvar,
                                on_cancelar=lambda: self._on_navigate("fornecedores"))
        btns.pack(anchor="e", padx=14, pady=(0,14))
    
    def _preencher(self, id_: int):
        f= FornecedorRepo.buscar_por_id(id_)
        if f:
            self._nome.set(f.nome)
    
    def _salvar(self):
        if not self._nome.validar():
            return
        
        try: 
            if self._fornecedor_id:
                EstoqueService.atualizar_fornecedor(self._fornecedor_id, self._nome.get())
                self._banner.sucesso("Fornecedor atualizado com sucesso.")
            else:
                EstoqueService.criar_fornecedor(self._nome.get())
                self._banner.sucesso("Fornecedor criado com sucesso.")
                self._nome.limpar()
                self._nome.focus()
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao salvar fornecedor: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")