"""
gui . telas . t02_inicio.py
Tela T-02- Tela inical/ Dashboard de situação
Sprint 1: KPIs reais com consultados do banco via MOD-06
"""

import logging
from datetime import date, datetime
from datetime import timedelta
from sqlalchemy.orm import joinedload
import customtkinter as ctk
from tkinter import messagebox
from sqlalchemy import func
from Modulo_06_dados import Movimentacao, get_read_session, Produto, Lote

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
    hoje= date.today()
    limite_15=  hoje+ timedelta(days=15)
    kpis={
        "produtos_ativos":  0,
        "lotes_vencidos":   0,
        "lotes_vencendo_15": 0,
        "estoque_baixo":    0,
        "mov_hoje":         0,
        "nomes_vencidos":   [],
        "nomes_vencendo_15":[],
    }

    try:
        with get_read_session() as session:
            #Produtos ativos
            kpis["produtos_ativos"]=(
                session.query(func.count(Produto.id))
                .filter(Produto.ativo==True)
                .scalar() or 0
            )

            lotes=(session.query(Lote)
                    .options(joinedload(Lote.produto)) # Carrega o nome do produto junto
                    .filter(Lote.quantidade_atual > 0)
                    .all())
            
            # Percorre lotes e identifica vencidos e prestes a vencer
            for l in lotes:
                detalhe= f"• {l.produto.nome} (Lote: {l.num_lote}) - Vence em: {l.data_vencimento.strftime('%d/%m/%Y')}"
                if l.data_vencimento<hoje:
                    kpis["lotes_vencidos"]+=1
                    kpis["nomes_vencidos"].append(detalhe)
                elif hoje<= l.data_vencimento<=limite_15:
                    kpis["lotes_vencendo_15"]+=1
                    kpis["nomes_vencendo_15"].append(detalhe)

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
        ctk.CTkLabel(topbar, text="Painel de situação",
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
        self._btn_detalhes=ctk.CTkButton(
            self._banner,text="Ver Detalhes", width=110, height=31,
            fg_color=COR_VERM,text_color="#FFFFFF",
            hover_color=COR_VERDE,font= ctk.CTkFont(size=11, weight="bold"),
            command= self._mostrar_detalhes_vencidos
        )
        self._btn_detalhes.pack(side="right", padx=10)

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
        ctk.CTkLabel(frame_tab,text="Lotes a vencer em 15 dias",
                     font=ctk.CTkFont(size=12,weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w",padx=14,pady=(10,4))
        self._lbl_tabela_15= ctk.CTkLabel(
            frame_tab,text="Carregando...",text_color="#888780",
            font=ctk.CTkFont(size=12), justify="left"
        )
        self._lbl_tabela_15.pack(anchor="w",padx=14,pady=(0,12))

    
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
        self._lista_vencidos=kpis.get("nomes_vencidos",[])

        if n_venc>0:
            self._lbl_banner.configure(
                text=f"ATENÇÂO {n_venc} lote(s) vencidos(s) com saldo em estoque\n", 
            )
            self._banner.pack(fill="x", padx=16, pady=10, before= self._frame_kpis)
        else:
            self._banner.pack_forget()
        
        # Tabela de lotes a vencer em 15 dias
        n_15=kpis.get("lotes_vencendo_15",0)
        if n_15>0: 
           lista_detalhada="\n".join(kpis.get("nomes_vencendo_15",[]))
           self._lbl_tabela_15.configure(
                text=f"Lotes vencendo em até 15 dias({n_15}):\n {lista_detalhada}"
           )
        else:
            self._lbl_tabela_15.configure(text="Nenhum lote a vencer nos proximos 15 dias.")
        
        #Timestamp
        self._timer=self.after(self.REFRESH_MS,self._atualizar)
    
    def _mostrar_detalhes_vencidos(self):
        """Abre uma janela (messagebox) com os detalhes dos lotes vencidos"""
        if hasattr(self, '_lista_vencidos') and self._lista_vencidos:
            detalhes = "\n".join(self._lista_vencidos)
            messagebox.showwarning(
                "Atenção - Lotes Vencidos", 
                f"Os seguintes lotes já passaram da data de validade:\n\n{detalhes}\n\nFavor realizar a retirada de estoque."
            )

    def destroy(self):
        """Cancela o timer ao destruir tela"""
        if self._timer:
            self.after_cancel(self._timer)
        super().destroy()