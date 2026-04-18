"""
gui . telas . t03_produto.py
Tela T-03 - Listagem de produtos - Técnico e ti
"""
import logging
import customtkinter as ctk

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
    ("Nome",      220),
    ("EAN",       140),
    ("Centro",    110),
    ("Marca",     110),
    ("Est.mín.",   70),
    ("Status",    110),
    ("Ações",     160),
]

def _centro_str(centro_alocacao) -> str:
    """
    Extrai o valor string do campo centro_alocacao independente de como
    o SQLAlchemy o retorna (pode ser Enum, string 'almoxarifado', ou
    string 'CentroAlocacaoEnum.almoxarifado' dependendo da versão).
    """
    val = str(centro_alocacao)
    # Se veio como 'CentroAlocacaoEnum.almoxarifado', pega só a parte após '.'
    if "." in val and not val.startswith("0"):
        val = val.split(".")[-1]
    return val.lower()


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
        self._entry_busca.pack(side="left")
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        self._opt_centro = ctk.CTkOptionMenu(
            filt, values=["Todos os centros","Almoxarifado", "Farmácia"],
            width=160, height=32, corner_radius=6,
            fg_color= COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a",
            command= lambda _: self._filtrar(),
        )
        self._opt_centro.pack(side="left", padx=8)

        ctk.CTkButton(filt, text="Limpar", width=70, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color= COR_CINZA_B,
                      hover_color= COR_CINZA_E,
                      command= self._limpar_filtros).pack(side="left")
        
        #Cabeçalho da tabela
        hdr= ctk.CTkFrame(self, fg_color="#FAFAF8", corner_radius=0,
                          border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10,0))
        for col,(txt,largura) in enumerate(_COLUNAS):
            ctk.CTkLabel(hdr, text= txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=largura, anchor="w").grid(row=0, column=col, padx=8, pady=6, stick="w")
        
        # Área scrollável de linhas
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=COR_BRANCO,
            border_width=1, border_color=COR_CINZA_B,
            corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0,16))
    
    def _carregar(self):
        try:
            self._produtos= EstoqueService.listar_produtos(apenas_ativos=False)
        except Exception as exc:
            logger.error("Erro ao carregar produtos: %s", exc)
            self._produtos=[]
        self._renderizar(self._produtos)
    
    def _filtrar(self):
        busca= self._entry_busca.get().lower()
        centro= self._opt_centro.get()
        filtrados=[]
        for p in self._produtos:
           nome_ok= busca in p.nome.lower() or busca in p.ean.lower()
           centro_ok=(
               centro =="Todos os centros"
               or _centro_str(p.centro_alocacao)==centro.lower()
           )
           if nome_ok and centro_ok:
            filtrados.append(p)

        
        self._renderizar(filtrados)
    
    def _limpar_filtros(self):
        self._entry_busca.delete(0,"end")
        self._opt_centro.set("Todos os centros")
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
            bg= COR_BRANCO if i % 2 == 0 else "#FAFAF8"
            row= ctk.CTkFrame(self._scroll, fg_color= bg, corner_radius=0)
            row.pack(fill="x")

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
            centro_label= _centro_str(p.centro_alocacao).capitalize()

            valores = [
                p.nome[:28],
                p.ean,
                centro_label,
                p.marca or "—",
                str(p.estoque_minimo),
            ]
            for col, (val, (_, largura)) in enumerate(zip(valores, _COLUNAS)):
                ctk.CTkLabel(
                    row, text=val, text_color="#3d3d3a",
                    font=ctk.CTkFont(size=12), width=largura, anchor="w",
                ).grid(row=0, column=col, padx=8, pady=7, sticky="w")

            
            fg,tc=_STATUS_COR.get(status, ("#F1EFE8", "#5F5E5A"))

            ctk.CTkLabel(row, text=status, 
                            fg_color=fg,text_color=tc,
                            font= ctk.CTkFont(size=10,weight="bold"), 
                            corner_radius=8, padx=5, pady=2, width=110, 
                            ).grid(row=0, column=(5), padx=8, pady=7, sticky="w")
            
            #Badge status
            ctk.CTkLabel(row, text=status, fg_color=fg, text_color=tc,
                         font=ctk.CTkFont(size=10,weight="bold"),
                         corner_radius=8, padx=8, pady=2,
                         width=100).grid(row=0, column=5, padx=8, pady=7, stick="w")
            
            # Ações
            acoes= ctk.CTkFrame(row, fg_color="transparent")
            acoes.grid(row=0, column=6, padx=8, pady=4, sticky="w")
            pid=p.id
            ctk.CTkButton(acoes, text="Editar", width=64, height=26,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B,
                          hover_color=COR_CINZA_E,
                          font=ctk.CTkFont(size=11),
                          command=lambda p= pid: self._on_navigate("editar_produto", extra=p)
                          ).pack(side="left", padx=(0,4))
            ctk.CTkButton(acoes, text="Ver lotes", width=72, height=26,
                          fg_color= COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color= COR_CINZA_B,
                          hover_color= COR_CINZA_E,
                          font=ctk.CTkFont(size=11),
                          command= lambda p=pid: self._on_navigate("posicao", extra=p)
                          ).pack(side="left")