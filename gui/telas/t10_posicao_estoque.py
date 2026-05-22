"""
gui · telas · t10_posicao_estoque.py
Tela T-10 — Posição atual do estoque por lote — todos os perfis (UC-07).
Exibe produto, lote, nota fiscal, saldo, vencimento e situação.
Ações de Entrada/Retirada disponíveis apenas para Técnico.
"""
import logging
from datetime import date, timedelta
from Modulo_06_dados import get_read_session, Produto, Lote
from sqlalchemy.orm import joinedload
import customtkinter as ctk

logger= logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERM   = "#A32D2D"

_SITUACAO_COR = {
    "Vencido":       ("#FCEBEB", "#A32D2D"),
    "Vence em 7d":   ("#FCEBEB", "#A32D2D"),
    "Vence em 15d":   ("#FAEEDA", "#854F0B"),
    "Vence em 30d":  ("#FAEEDA", "#854F0B"),
    "Estoque baixo": ("#FAEEDA", "#854F0B"),
    "Normal":        ("#EAF3DE", "#27500A"),
}

_COLUNAS = [
    ("Produto",     180),
    ("Lote",         90),
    ("Nota Fiscal",  90),
    ("Centro",       90),
    ("Qtd atual",    80),
    ("Vencimento",  100),
    ("Situação",    120),
    ("Ações",       150),
]


def _calcular_situacao(lote, estoque_minimo:int, hoje:date)->str:
    if lote.data_vencimento<hoje:
        return "Vencido"
    diff=(lote.data_vencimento-hoje).days
    if diff<= 7 :
        return "Vence em 7d"
    if diff<= 15 and diff>7:
        return "Vence em 15d"
    if diff<= 30 and diff>15:
        return"Vence em 30d"
    if lote.quantidade_atual<= estoque_minimo:
        return"Estoque baixo"
    return"Normal"

class TelaPosicaoEstoque(ctk.CTkFrame):
    #posição atual do estoque por lote- somente leitura para TI, com ações para administração e Tecnico
    def __init__(self, master, usuario, on_navigate, produto_id:int=None):
        super().__init__(master,fg_color=COR_CINZA_E,corner_radius=0)
        self._usuario = usuario
        self._on_navigate= on_navigate
        self._produto_id= produto_id
        self._linhas= [] #(lote, produto, situacao)
        self.permissao= usuario.perfil.value=="tecnico", "admin"
        self._construir()
        self._carregar()

    #___ Construçãp_________________________________________________________________________________________
    def _construir(self):
        topbar=ctk.CTkFrame(self,fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Estado atual do estoque",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(topbar, text="atualizar", width=90, height=28,
                      fg_color=COR_BRANCO, text_color="#161614",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._carregar).pack(side="right", padx=16, pady=8)
        
        #Filtros
        filt= ctk.CTkFrame(self, fg_color="transparent")
        filt.pack(fill="x", padx=16, pady=(10,0))

        self._entry_busca= ctk.CTkEntry(
            filt, placeholder_text="Buscar produto ou lote",
            height=32, width=260, corner_radius=6)
        self._entry_busca.pack(side="left")
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        self._opt_centro= ctk.CTkOptionMenu(
            filt, values=["Todos os centros", "Almoxarifado", "Farmacia","Deposito"],
            width=150, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color= COR_AZUL_M, text_color="#161614",
            command=lambda _: self._filtrar())
        self._opt_centro.pack(side="left", padx=8)

        self._opt_situacao= ctk.CTkOptionMenu(
            filt,
            values=["Todas as situações", "Normal", "Estoque baixo", 
                    "Vence em 30d", "Vence em 15d", "Vence em 7d", "Vencido"],
                    width=170, height=32, corner_radius=6,
                    fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#161614",
                    command=lambda _: self._filtrar())
        self._opt_situacao.pack(side="left", padx=(0,8))

        ctk.CTkButton(filt, text="limpar", width=70, height=32,
                      fg_color=COR_BRANCO, text_color="#161614",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command= self._limpar_filtros).pack(side="left")
        
        #Cabeçalho
        hdr=ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=0,
                         border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10,0))
        for col,(txt, largura) in enumerate(_COLUNAS):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=9, weight="bold"),
                         width=largura, anchor="w"
                         ).grid(row=0, column=col, padx=6, pady=5, sticky="w")
        

        self._scroll=ctk.CTkScrollableFrame(
            self, fg_color=COR_BRANCO,
            border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0,16))
        
        self._lbl_rodape= ctk.CTkLabel(
            self, text="", text_color="#888780", font=ctk.CTkFont(size=10))
        self._lbl_rodape.pack(anchor="w", padx=18, pady=(0,8))
    
    
    #___________Dados___________________________________________________________________
    def _carregar(self):
        try:
            hoje= date.today()
            with get_read_session() as s:
                query=(
                    s.query(Lote)
                    .join(Produto)
                    .options(joinedload(Lote.produto))
                    .filter(Produto.ativo==True)
                )
                if self._produto_id:
                    query=query.filter(Lote.produto_id==self._produto_id)

                lotes= query.order_by(Produto.nome, Lote.data_vencimento).all()

                #Calcular situação e saldo por produto
                saldo_por_produto: dict[int,int]={}
                for l in lotes:
                    if l.quantidade_atual>0 and l.data_vencimento>= hoje:
                        saldo_por_produto[l.produto_id]=(
                            saldo_por_produto.get(l.produto_id,0)+ l.quantidade_atual)
                
                self._linhas=[]
                for l in lotes:
                    if l.quantidade_atual==0 and l.data_vencimento< hoje:
                        continue #pular lotes esgotados e vencidos
                    sit= _calcular_situacao(l, l.produto.estoque_minimo, hoje)
                    # Sobrepor com estoque baixo se aplicavel
                    if sit=="Normal":
                        saldo_total= saldo_por_produto.get(l.produto_id, 0)
                        if(l.produto.estoque_minimo>0
                           and saldo_total<= l.produto.estoque_minimo):
                            sit="Estoque baixo"
                    self._linhas.append((l, l.produto,sit))
                
                s.expunge_all()
        
        except Exception as exc:
            logger.error("Erro ao carregar posição estoque: %s", exc)
            self._erro_na_tela(str(exc))
            return

        self._renderizar(self._linhas)
    
    def _filtrar(self):
        busca = self._entry_busca.get().lower()
        centro= self._opt_centro.get()
        situacao= self._opt_situacao.get()

        filtrados=[
            (l,p,s) for l, p, s in self._linhas
            if (busca in p.nome.lower() or busca in l.num_lote.lower() or busca in l.nota_fiscal.lower())
            and(centro=="Todos os centros" or p.centro_alocacao.value.lower() in centro.lower())
            and (situacao== "Todas as situações" or s == situacao)
        ]
        self._renderizar(filtrados)
    

    def _limpar_filtros(self):
        self._entry_busca.delete(0,"end")
        self._opt_centro.set("Todos os centros")
        self._opt_situacao.set("todas as situações")
        self._renderizar(self._linhas)

    
    #_______Renderização______________________________________________________

    def _renderizar(self, linhas):
        for w in self._scroll.winfo_children():
            w.destroy()
        
        if not linhas:
            ctk.CTkLabel(self._scroll, text="Nenhum lote encontrado.",
                        text_color=COR_VERM,
                        font= ctk.CTkFont(size=12)).pack(pady=24)
            self._lbl_rodape.configure(text="")
            return
        
        for i, (lote, produto, situacao) in enumerate(linhas):
            bg=COR_BRANCO if i%2 ==0 else "#A1C3E4"
            row= ctk.CTkFrame(self._scroll,fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            valores=[
                (produto.nome[:22], 180),
                (lote.num_lote,      90),
                (lote.nota_fiscal,   90),
                (lote.centro_alocacao.value.capitalize(), 90),
                (str(lote.quantidade_atual), 80),
                (lote.data_vencimento.strftime("%d/%m/%Y"), 100),
            ]
            for col,(val,largura) in enumerate(valores):
                ctk.CTkLabel(row, text=val, text_color="#3d3d3a",
                             font=ctk.CTkFont(size=11), width=largura,
                             anchor="w").grid(
                    row=0, column=col, padx=6, pady=6, sticky="w")
            
            # Badge situação
            fg_s, tc_s= _SITUACAO_COR.get(situacao,("#F1EFE8", "#5F5E5A"))
            ctk.CTkLabel(row, text=situacao,
                         fg_color=fg_s, text_color=tc_s,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         corner_radius=6,padx=6,pady=2, width=120
                         ).grid(row=0, column=6, padx=6, pady=6, sticky="w")
            
            #Ações- 
            acoes= ctk.CTkFrame(row, fg_color="transparent")
            acoes.grid(row=0,column=7, padx=6, pady=4, sticky="w")
            
            if self.permissao:
                pid= produto.id
                ctk.CTkButton(
                    acoes, text="Entrada", width= 64, height=26, 
                    fg_color=COR_BRANCO, text_color="#3d3d3a",
                    border_width= 1, border_color=COR_CINZA_B,
                    hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11), 
                    command=lambda p=pid: self._on_navigate("entrada_manual",extra=p)
                ).pack(side="left", padx=(0,4))


                #Retirada bloqueada para lotes vencidos
                pode_retirar= situacao!= "Vencido"
                ctk.CTkButton(
                    acoes, text="Retirada", width=64, height=26,
                    fg_color=COR_BRANCO, text_color="#3d3d3a" if pode_retirar else "#AAAAAA",
                    border_width=1, border_color=COR_CINZA_B,
                    hover_color=COR_CINZA_E if pode_retirar else COR_BRANCO,
                    font= ctk.CTkFont(size=11),
                    state="normal" if pode_retirar else "disabled",
                    command=(lambda p=pid: self._on_navigate("retirada", extra=p))
                    if pode_retirar else None,
                ).pack(side="left")
        
        vencidos=  sum(1 for _,_,s in linhas if s=="Vencido")
        self._lbl_rodape.configure(
            text=f"{len(linhas)} lotes(s) exibidos"+ (f". {vencidos} vencidos" if vencidos else"")
        )

    def _erro_na_tela(self, detalhe:str):
        for w in self._scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._scroll,
                     text=f"Erro ao carregar estoque: \n {detalhe}",
                     text_color= COR_VERM, font=ctk.CTkFont(size=12),
                     wraplength=600, justify="left").pack(pady=24, padx=16)