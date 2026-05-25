"""
gui . telas . t03_produto.py
Tela T-03 - Listagem de produtos - Técnico e ti
"""
import logging
import customtkinter as ctk
import tkinter as tk
from Modulo_02_estoque import EstoqueService
from Modulo_02_estoque import LoteRepo
from datetime import date

logger= logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_AZUL_L = "#D6E4F0"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERDE  = "#1D9E75"
COR_AMBER  = "#BA7517"
COR_VERM   = "#A32D2D"

_STATUS_COR={
     "Ativo":          ("#EAF3DE", "#27500A"),
    "Inativo":        ("#F1EFE8", "#5F5E5A"),
    "Estoque baixo":  ("#FAEEDA", "#854F0B"),
}

# Colunas: (header, largura)
_COLUNAS = [
    ("Nome",      300),
    ("EAN",       150),
    ("Marca",     220),
    ("Est.mín.",   80),
    ("Saldo",      80),
    ("Status",    300),
    ("Ações",     200),
]

class TelaProdutos(ctk.CTkFrame):
    """Listagem de produtos com filtros e ações de navegação"""

    def __init__(self, master, usuario,on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._produtos    = []
        self._construir()
        self._carregar()

    def _construir(self):
        #Topbar
        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Produtos",
                     font= ctk.CTkFont(size=13, weight="bold"),
                     text_color= COR_AZUL).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(topbar, text="+ Novo produto", width=130, height= 28,
                      fg_color= COR_AZUL_M, hover_color="#1a5276",
                      font= ctk.CTkFont(size=12),
                      command=lambda: self._on_navigate("novo_produto")).pack(side="right", padx=16, pady=8)
        
        #filtros
        filt= ctk.CTkFrame(self, fg_color="transparent")
        filt.pack(fill="x", padx=16, pady=(10,0))

        self._entry_busca= ctk.CTkEntry(filt, placeholder_text="Buscar por nome ou EAN...",
                                    height=32, width= 300, corner_radius=6)
        self._entry_busca.pack(side="left", padx=(0,8))
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        ctk.CTkButton(filt, text="Limpar", width=70, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color= COR_CINZA_B,
                      hover_color= COR_CINZA_E,
                      command= self._limpar_filtros).pack(side="left")
        
        #Cabeçalho da tabela
        hdr= ctk.CTkFrame(self, fg_color="#FAFAF8", corner_radius=0,
                          border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10,0))
        hdr.grid_columnconfigure(5, weight=1) # Status expande para ocupar espaço extra, alinhado à esquerda)
        
        for col, (txt, largura) in enumerate(_COLUNAS):
            # Títulos alinhados ao centro, com exceção de "Ações" que cola na direita
            if col == 6: # Ações -> extrema direita
                ancora = "e"
                stick  = "e"
            elif col in (3, 4, 5): # Est.min, Saldo E STATUS -> centralizados
                ancora = "center"
                stick  = "ew"
            else: # Restante -> esquerda
                ancora = "w"
                stick  = "w"

            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=largura, anchor=ancora
                         ).grid(row=0, column=col, padx=8, pady=6, sticky=stick)
            
        # Área scrollável de linhas
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=COR_BRANCO,
            border_width=1, border_color=COR_CINZA_B,
            corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0,16))
    
    def _carregar(self):
        try:
            self._produtos= EstoqueService.listar_produtos(apenas_ativos=True)
        except Exception as exc:
            logger.error("Erro ao carregar produtos: %s", exc)
            self._produtos=[]
        self._renderizar(self._produtos)
    
    def _filtrar(self):
        busca= self._entry_busca.get().lower()
        filtrados=[]
        for p in self._produtos:
           nome_ok= busca in p.nome.lower() or busca in p.ean.lower()
           if nome_ok :
            filtrados.append(p)

        
        self._renderizar(filtrados)
    
    def _limpar_filtros(self):
        self._entry_busca.delete(0,"end")
        self._renderizar(self._produtos)
    
    def _renderizar(self, produtos):
        for w in self._scroll.winfo_children():
            w.destroy()
        
        if not produtos:
            ctk.CTkLabel(
                self._scroll,
                text="Nenhum produto encontrado",
                text_color="#888780",
                font= ctk.CTkFont(size=12),
            ).pack(pady=24)
            return
        
        hoje= date.today()

        for i, p in enumerate(produtos):
            bg= COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row= ctk.CTkFrame(self._scroll, fg_color= bg, corner_radius=0)
            row.pack(fill="x")

            row.grid_columnconfigure(5, weight=1)

            # Calcular saldo atual
            try:
                lotes = LoteRepo.listar_por_produto(p.id)
                saldo = sum(l.quantidade_atual for l in lotes if l.data_vencimento >= hoje)
            except Exception:
                saldo = 0
                
            # Calcular status
            if not p.ativo:
                status="Inativo"
            else:
                try:
                    lotes = LoteRepo.listar_por_produto(p.id)
                    saldo=sum(l.quantidade_atual for l in lotes if l.data_vencimento>=hoje)
                    status=("Estoque baixo" if p.estoque_minimo>0 and saldo <= p.estoque_minimo else "Ativo")
                except Exception:
                    status="Ativo"
            

            valores = [
                p.nome[:28],
                p.ean,
                p.marca or "—",
                str(p.estoque_minimo),
                str(saldo),
            ]
            for col, (val, (_, largura)) in enumerate(zip(valores, _COLUNAS)):
                if col == 5:
                    ctk.CTkFrame(row, width=20, height=0, fg_color="transparent").grid(row=0, column=7) # Ações -> extrema direita
                if col in (3, 4, 5): 
                    stick = "ew"
                    justifica = "center"
                else:            
                    stick = "w"
                    justifica = "left"

                ctk.CTkEntry(row,
                                textvariable=tk.StringVar(value=val),
                                state="readonly",
                                justify=justifica, # Define alinhamento do texto
                                text_color="#3d3d3a",
                                fg_color="transparent",
                                border_width=0,
                                font=ctk.CTkFont(size=12),
                                width=largura
                                ).grid(row=0, column=col, padx=8, pady=7, sticky=stick)
                    

            
            fg,tc=_STATUS_COR.get(status, ("#F1EFE8", "#5F5E5A"))

            
            
            largura_status = _COLUNAS[5][1] 
            frame_status = ctk.CTkFrame(row, fg_color="transparent", width=largura_status, height=26)
            frame_status.pack_propagate(False) 
            frame_status.grid(row=0, column=5, padx=8, pady=2, sticky="w")
            
            # Badge de Status (Fica centralizado no meio do "espaço vazio")
            ctk.CTkLabel(row, text=status, fg_color=fg, text_color=tc,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         corner_radius=8, padx=8, pady=2, width=80
                         ).grid(row=0, column=5, padx=8, pady=2)

            '''
            #Badge status
            ctk.CTkLabel(row, text=status, fg_color=fg, text_color=tc,
                         font=ctk.CTkFont(size=10,weight="bold"),
                         corner_radius=8, padx=8, pady=2,
                         width=1).grid(row=0, column=5, padx=8, pady=2)
                         '''
            
           # --- COLUNA 6: AÇÕES ---
            largura_acoes = _COLUNAS[6][1] 
            acoes = ctk.CTkFrame(row, fg_color="transparent", width=largura_acoes, height=30)
            
            # sticky="e" (East) cola todo o bloco de botões na extrema direita
            acoes.grid(row=0, column=6, padx=8, pady=4, sticky="e")
            
            pid = p.id
            ctk.CTkButton(acoes, text="Editar", width=64, height=26,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B,
                          hover_color=COR_CINZA_E,
                          font=ctk.CTkFont(size=11),
                          command=lambda p=pid: self._on_navigate("editar_produto", extra=p)
                          ).pack(side="left", padx=(0,4))
                          
            ctk.CTkButton(acoes, text="Ver lotes", width=72, height=26,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B,
                          hover_color=COR_CINZA_E,
                          font=ctk.CTkFont(size=11),
                          command=lambda p=pid: self._on_navigate("posicao", extra=p)
                          ).pack(side="left")
            saldo = 0