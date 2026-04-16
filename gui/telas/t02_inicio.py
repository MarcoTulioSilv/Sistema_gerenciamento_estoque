"""
gui . telas . t02_inicio.py
Tela T-02- Tela inical/ Dashboard de situação
Sprint 1: KPIs reais com consultados do banco via MOD-06
"""

import logging
from datetime import date, datetime
from datetime import timedelta

import customtkinter as ctk
from tkinter import messagebox

from Modulo_06_dados import Movimentacao

logger= logging.getLogger(__name__)

COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_AZUL_L  = "#D6E4F0"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_VERDE   = "#1D9E75"
COR_AMBER   = "#BA7517"
COR_VERM    = "#A32D2D"
COR_BRANCO  = "#FFFFFF"

def _consultar_kpis()->dict:
    """
    Consulta os KPIs de situação de estoque no banco
    Retorna dicionário com contagens para exibição nos cards.
    """
    from Modulo_06_dados import get_read_session,Produto,Lote
    from sqlalchemy import func

    hoje= date.today()
    kpis={
        "produtos_ativos":  0,
        "lotes_vencidos":   0,
        "lotes_vencidos_7": 0,
        "estoque_baixo":    0,
        "mov_hoje":         0,
        "nomes_vencidos":   [],
    }

    try:
        with get_read_session() as session:
            #Produtos ativos
            kpis["produtos_ativos"]=(
                session.query(func.count(Produto.id))
                .filter(Produto.ativo==True)
                .scalar() or 0
            )

            #Lotes Vencidos com saldo > 0
            lotes_vencidos=(
                session.query(Lote)
                .join(Produto)
                .filter(
                    Lote.data_vencimento<hoje,
                    Lote.quantidade_atual>0,
                    Produto.ativo==True,
                )
                .all()
            )
            kpis["lotes_vencidos"]= len(lotes_vencidos)
            kpis["nomes_vencidos"]=[
              f"{l.produto.nome} · {l.num_lote}" for l in lotes_vencidos[:5]
            ]

            #Lotes vencendo em até 7 dias
            limite= hoje+timedelta(days=7)
            kpis["lotes_vencidos_7"]=(
                session.query(func.count(Lote.id))
                .join(Produto)
                .filter(
                    Lote.data_vencimento>=hoje,
                    Lote.data_vencimento<=limite,
                    Lote.quantidade_atual>0,
                    Produto.ativo==True,
                )
                .scalar() or 0
            )

            #Produtos com estoque abaixo do mínimo
            todos_produtos=(
                session.query(Produto)
                .filter(Produto.ativo==True,Produto.estoque_minimo>0)
                .all()
            )
            for prod in todos_produtos:
                saldo=sum(
                    l.quantidade_atual for l in prod.lotes
                    if l.quantidade_atual>0 and l.data_vencimento>=hoje
                )
                if saldo<= prod.estoque_minimo:
                    kpis["estoque_baixo"]+=1
            
            #Movimentações do dia
            inicio_hoje= datetime.combine(hoje,datetime.min.time())
            kpis["mov_hoje"]=(
                session.query(func.count(Movimentacao.id))
                .filter(Movimentacao.data_hora>=inicio_hoje)
                .scalar() or 0
            )
    except Exception as exc:
        logger.error("Erro ao consultar KPIs:%s",exc)
    return kpis

class TelaInicio(ctk.CTkFrame):
    """Tela inicial com KPIs e Painel de alertas- UC-07, UC-17,RF-22."""

    REFRESH_MS=120_000 # atualiza KPIs a cada 2 minutos

    def __init__(self,master,usuario):
        super().__init__(master,fg_color=COR_CINZA_E,corner_radius=0)
        self._usuario = usuario
        self._timer   = None
        self._construir()
        self._atualizar()
    
    def _construir(self):
        #Topbar
        topbar= ctk.CTkFrame(self,fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Inicio-Painel de situação",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color= COR_AZUL).pack(side="left", padx=16, pady=10)
        self._lbl_ts = ctk.CTkLabel(topbar, text="", text_color="#888780", 
                                         font= ctk.CTkFont(size=11))
        self._lbl_ts.pack(side="right", padx=16)

        #Banner de lotes vencidos(oculto por padrão)
        self._banner= ctk.CTkFrame(self, fg_color="#FCEBEB", corner_radius=6,
                               border_width=1, border_color="#F09595")
        self._lbl_banner= ctk.CTkLabel(
            self._banner, text="", text_color=COR_VERM,
            font=ctk.CTkFont(size=12), wraplength=800,justify="left"
        )
        self._lbl_banner.pack(side="left",padx=14,pady=8)
        ctk.CTkButton(
            self._banner,text="Ver Detalhes →", width=100, height=26,
            fg_color="transparent",text_color=COR_AZUL_M,
            hover_color=COR_AZUL_L,font= ctk.CTkFont(size=11),
        ).pack(side="left",padx=10)

        #Grid de KPIs cards
        self._frame_kpis= ctk.CTkFrame(self, fg_color="transparent")
        self._frame_kpis.pack(fill="x",padx=16,pady=(12,0))
        for i in range(4):
            self._frame_kpis.grid_columnconfigure(i,weight=1)
        
        self._cards={}
        specs=[
            ("produtos_ativos",  "Produtos ativos",          COR_AZUL, ""),
            ("lotes_vencidos",   "Lotes vencidos",           COR_VERM, ""),
            ("estoque_baixo",    "Estoque abaixo do mínimo", COR_AMBER, "produtos"),
            ("mov_hoje",         "Movimentações hoje",       COR_AZUL,  "entradas + saídas"),
        ]

        for col,(chave,titulo,cor,sub) in enumerate(specs):
            card= ctk.CTkFrame( self._frame_kpis, fg_color=COR_BRANCO,
                               corner_radius=8,border_width= 1, border_color=COR_CINZA_B)
            card.grid(row=0,column=col,padx=(0 if col==0 else 8,0), pady=0, sticky="ew")
            ctk.CTkLabel(card, text=titulo.upper(),
                         text_color="#888780",
                         font=ctk.CTkFont(size=9,weight="bold")).pack(anchor="w",padx=14,pady=(12,0))
            lbl_val= ctk.CTkLabel(card, text="—",text_color=cor,
                                  font=ctk.CTkFont(size=28,weight="bold"))
            lbl_val.pack(anchor="w",padx=14)
            ctk.CTkLabel(card,text=sub,text_color="#888780",
                         font=ctk.CTkFont(size=11)).pack(anchor="w",padx=14,pady=(0,12))
            self._cards[chave]=lbl_val

        #Tabela vencimentos próximos
        frame_tab= ctk.CTkFrame(self,fg_color=COR_BRANCO,corner_radius=8,
                                border_width=1,border_color=COR_CINZA_B)
        frame_tab.pack(fill="both", expand=True, padx=16,pady=12)
        ctk.CTkLabel(frame_tab,text="Lotes a vencer em 7 dias",
                     font=ctk.CTkFont(size=12,weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w",padx=14,pady=(10,4))
        self._lbl_tabela= ctk.CTkLabel(
            frame_tab,text="Carregando...",text_color="#888780",
            font=ctk.CTkFont(size=12), justify="left"
        )
        self._lbl_tabela.pack(anchor="w",padx=14,pady=(0,12))
    
    def _atualizar(self):
        """Consulta KPIs e atualiza a interface"""
        try:
            kpis= _consultar_kpis()
        except Exception as exc:
            logger.error("Falha ao atualizar KPIs:%s",exc)
            kpis={}
        
        #atualiza cards
        for chave, lbl in self._cards.items():
            lbl.configure(text=str(kpis.get(chave,"—")))
        
        # Banner de vencidos
        n_venc= kpis.get("lotes_vencidos",0)
        if n_venc>0:
            nomes="\n".join(kpis.get("nomes_vencidos",[]))
            self._lbl_banner.configure(
                text=f"{n_venc} lote(s) vencidos(s) com saldo em estoque\n{nomes}"
            )
        else:
            self._banner.pack_forget()
        
        # Tabela de lotes a vencer emm 7 dias
        n_7=kpis.get("lotes_vencendo_7",0)
        if n_7>0: 
            self._lbl_tabela.configure(
                text=f"{n_7} lote(s) com vencimento nos próximos 7 dias. Acesse Posição do estoque para mais detalhes."
            )
        else:
            self._lbl_tabela.configure(text="Nenhum lote a vencer nos proximos 7 dias.")
        
        #Timestamp
        self._timer=self.after(self.REFRESH_MS,self._atualizar)
    
    def destroy(self):
        """Cancela o timer ao destruir tela"""
        if self._timer:
            self.after_cancel(self._timer)
        super().destroy()