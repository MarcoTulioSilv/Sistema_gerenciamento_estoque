"""
gui · telas · t04_fornecedores.py
Tela T-04 — Listagem de fornecedores — Técnico e TI (RF-23).
"""
import logging
import customtkinter as ctk

from Modulo_02_estoque import EstoqueService
#from Modulo_02_estoque import FornecedorRepo

logger = logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"

class TelaFornecedores(ctk.CTkFrame):

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._fornecedores = []
        self._construir()
        self._carregar()

    def _construir(self):
        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Fornecedores",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
        ctk.CTkButton(topbar, text="+ Novo fornecedor", width=150, height=28,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      font=ctk.CTkFont(size=12),
                      command=lambda: self._on_navigate("novo_fornecedor")
                      ).pack(side="right", padx=16, pady=8)
        # Busca
        filt = ctk.CTkFrame(self, fg_color="transparent")
        filt.pack(fill="x", padx=16, pady=10)
        self._entry_busca = ctk.CTkEntry(filt, placeholder_text="Buscar por nome...",
                                          height=32, width=300, corner_radius=6)
        self._entry_busca.pack(side="left")
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color="#FAFAF8", corner_radius=0,
                            border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16)
        for col, (txt, w) in enumerate([("ID", 60), ("Nome", 400), ("Produtos", 120), ("Ações", 100)]):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=w, anchor="w").grid(row=0, column=col, padx=10, pady=6, sticky="w")
        
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=COR_BRANCO,
            border_width=1, border_color=COR_CINZA_B, corner_radius=0,)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0,16))
    
    def _carregar(self):
        try:
            self._fornecedores = EstoqueService.listar_fornecedores()
            self._renderizar(self._fornecedores)
        except Exception as exc:
            logger.error("Erro ao carregar fornecedores: %s", exc)
            self._renderizar(self._fornecedores)
    
    def _filtrar(self):
        busca= self._entry_busca.get().strip().lower()
        self._renderizar([f for f in self._fornecedores if busca in f.nome.lower()])
    
    def _renderizar(self, fornecedores):
        for w in self._scroll.winfo_children():
            w.destroy()
        if not fornecedores:
            ctk.CTkLabel(self._scroll, text="Nenhum fornecedor encontrado.",
                         font=ctk.CTkFont(size=12), text_color="#888780").pack(pady=20)
            return
        
        for i,f in enumerate(fornecedores):
            bg= COR_BRANCO if i % 2 == 0 else "#FAFAF8"
            row= ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")
            n_prod= FornecedorRepo.contar_produtos(f.id)
            for col, (val,w) in enumerate([
                (str(f.id), 60), (f.nome, 400),(f"{n_prod} produto(s)", 120),
            ]):
                ctk.CTkLabel(row, text= val, text_color="#3d3d3a",
                             font=ctk.CTkFont(size=12), width= w,
                             anchor="w").grid(row=0, column=col, padx=10, pady=7, sticky="w")
            fid=f.id
            ctk.CTkButton(row, text="Editar", width=70, height=26,
                        fg_color=COR_BRANCO, text_color="#3d3d3a",
                        border_width=1, border_color=COR_CINZA_B,
                        hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                        command=lambda fid=fid: self._on_navigate("editar_fornecedor", extra=fid)
                        ).grid(row=0, column=3, padx=10, pady=5, sticky="w")