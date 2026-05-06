"""
gui · telas · t22_dashboard.py
Tela T-22 — Dashboard de monitoramento em tempo real (RF-24).
Somente leitura. Auto-refresh via after(). Técnico e Gestora.
"""

import logging
import os
from datetime import date, datetime, timedelta
from Modulo_06_dados import get_read_session, Produto,Lote
from sqlalchemy.orm import joinedload
import customtkinter as ctk
logger = logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERDE  = "#1D9E75"
COR_AMBER  = "#BA7517"
COR_VERM   = "#A32D2D"


def _buscar_dados_dashboard()->dict:
    #Consulta todos os dados necessário para dashboard em uma única sessão.
    hoje= date.today()
    resultado = {
        "vencidos":    [],
        "vence_7d":    [],
        "vence_15d":    [],
        "vence_30d":   [],
        "baixo":       [],
        "normais":     0,
        "total_lotes": 0,
        "ts":          datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "erro":        None,
    }
    
    try: 
        with get_read_session() as s:
            lotes=(
                s.query(Lote)
                .join(Produto)
                .options(joinedload(Lote.produto))
                .filter(Produto.ativo==True, Lote.quantidade_atual>0)
                .order_by(Lote.data_vencimento)
                .all()
            )

            #saldo por produto para calcular estoque baixo
            saldo_prod: dict[int, int]={}
            for l in lotes:
                if l.data_vencimento>=hoje:
                    saldo_prod[l.produto_id]=(
                    saldo_prod.get(l.produto_id,0)+ l.quantidade_atual)
            
            resultado["total_lotes"]=len(lotes)

            for l in lotes:
                nome= f"{l.produto.nome[:24]} | Lote: {l.num_lote}"
                diff=(l.data_vencimento-hoje).days

                if l.data_vencimento<hoje:
                    resultado["vencidos"].append(nome)
                elif diff<=7:
                    resultado["vence_7d"].append(
                        f"{nome} ({diff}d)")
                elif diff<=15:
                    resultado["vence_15d"].append(
                        f"{nome} ({diff}d)")
                elif diff<=30:
                    resultado["vence_30d"].append(
                        f"{nome} ({diff}d)")
                else:
                    resultado["normais"]+=1

            #estoque baixo(por produto, não por lote)
            vistos:set[int]=set()
            for l in lotes:
                pid=l.produto_id
                if pid in vistos:
                    continue
                vistos.add(pid)
                minimo= l.produto.estoque_minimo
                if minimo >0:
                    saldo= saldo_prod.get(pid,0)
                    if saldo<=minimo:
                        resultado["baixo"].append(
                            f"{l.produto.nome[:24]}\n"
                            f"{saldo}/{minimo}")

            s.expunge_all()
    
    except Exception as exc:
        logger.error("Erro ao buscar dados dashboard: %s", exc)
        resultado["erro"]=str(exc)
    return resultado

class TelaDashboard(ctk.CTkFrame):
    #Dashboard de monitoramento em tempo real- some leitura(RF-24)

    REFRESH_PADRAO_MS=120_000
    
    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario= usuario
        self._on_navigate= on_navigate
        self._timer= None
        self._refresh_ms= int(os.getenv("DASHBOARD_REFRESH_SEC",30))*1000
        self._construir()
        self._atualizar()
    
    #___Construção________________________________________________________________

    def _construir(self):
        # toolbar
        toolbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=40, corner_radius=0)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        ctk.CTkLabel(toolbar, text="Dashboard de monitoramento",
                     font=ctk.CTkFont(size=13,weight="bold"),
                     text_color= COR_AZUL).pack(side="left", padx=16)
        
        self._lbl_conexao= ctk.CTkLabel(
            toolbar, text="● Conectado",
            text_color=COR_VERDE, font=ctk.CTkFont(size=11))
        self._lbl_conexao.pack(side="left", padx=16)

        self._lbl_ts=ctk.CTkLabel(toolbar,
                                  text="", text_color="#888780",
                                  font=ctk.CTkFont(size=11))
        self._lbl_ts.pack(side="right", padx=8)

        ctk.CTkLabel(toolbar, text="Somente leitura",
                     text_color="#AAAAAA", font=ctk.CTkFont(size=10)
                     ).pack(side="right", padx=4)
        
        #Grid de cards- 3 columas
        self._grid= ctk.CTkFrame(self, fg_color=COR_CINZA_E)
        self._grid.pack(fill="both", expand=True, padx=12, pady=10)
        for c in range(3):
            self._grid.grid_columnconfigure(c,weight=1)

         # Criar 6 cards fixos
        self._cards: dict[str, "_CardDash"] = {}
        specs = [
            ("vencidos",  "⚠ Lotes vencidos",         COR_VERM,  0, 0),
            ("vence_7d",  "Vencimento em 2 dias",      COR_VERM,  0, 1),
            ("vence_15d",  "Vencimento em 7 dias",      COR_AMBER, 0, 2),
            ("vence_30d", "Vencimento em 15 dias",     COR_VERDE, 1, 1),
            ("normais",   "Situação normal",           COR_VERDE, 1, 2),
            ("baixo",     "Estoque abaixo do mínimo",  COR_AMBER, 1, 0)]
        
        for chave, titulo, cor, row, col in specs:
            card= _CardDash(self._grid, titulo, cor_titulo=cor)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._cards[chave]=card
        
        self._grid.grid_rowconfigure(0,weight=1)
        self._grid.grid_rowconfigure(1, weight=1)
    
    #__________ Atualização______________________________________________________
    def _atualizar(self):
        dados=_buscar_dados_dashboard()

        if dados["erro"]:
            self._lbl_conexao.configure(text="● Desconectado",text_color=COR_VERM)
        else:
            self._lbl_conexao.configure(text="● Conectado", text_color=COR_VERDE)
        
        self._lbl_ts.configure(text=f"Atualizado:{dados['ts']}")

        # Preencher cards
        for chave in("vencidos","vence_7d","vence_15d", "vence_30d", "baixo"):
            itens=dados.get(chave,[])
            self._cards[chave].atualizar(itens)
        
        n_norm= dados.get("normais",0)
        total= dados.get("total_lotes", 0)
        self._cards["normais"].atualizar_texto(
            f"{n_norm} lote(s) sem ocorrências.",
            f"Total de lotes ativos com saldo:{total}"
        )

        #Agendar próxima atualização
        if self._timer:
            self.after_cancel(self._timer)
        if self._refresh_ms>0:
            self._timer= self.after(self._refresh_ms, self._atualizar)
    
    def destroy(self):
        if self._timer:
            self.after_cancel(self._timer)
        super().destroy()


class _CardDash(ctk.CTkFrame):
    #Card individuaç do dashboard com lista de itens scrollável.
    
    def __init__(self,master, titulo: str, cor_titulo: str, **kwargs):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=8,
                         border_width=1, border_color= COR_CINZA_B, **kwargs)
        self._cor_titulo=cor_titulo

        self._lbl_titulo= ctk.CTkLabel(
            self, text=titulo, font=ctk.CTkFont(size=12,weight="bold"),
            text_color=cor_titulo, anchor="w")
        self._lbl_titulo.pack(fill="x", padx=12, pady=(10,0))

        ctk.CTkFrame(self, fg_color=COR_CINZA_B, height=1).pack(
            fill="x", padx=12, pady=(4,6))
        
        self._scroll= ctk.CTkScrollableFrame(
            self, fg_color="transparent", height=120, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(0,8))
    
    def atualizar(self, itens: list[str]):
        #Atualiza a lista de itens no card.
        for w in self._scroll.winfo_children():
            w.destroy()
        
        self._lbl_titulo.configure(
            text=f"{self._lbl_titulo.cget('text').split('(')[0].strip()} ({len(itens)})"
        )

        if not itens:
            ctk.CTkLabel(self._scroll, text="Nenhuma ocorrência.",
                         text_color="#AAAAAA",
                         font=ctk.CTkFont(size=11)).pack(anchor="w", pady=4)
            return
        
        for item in itens:
            ctk.CTkLabel(self._scroll, text=f"• {item}",
                         text_color="#3d3d3a",
                         font=ctk.CTkFont(size=11),
                         anchor="w", justify="left",
                         wraplength=280).pack(fill="x", pady=2)

    def atualizar_texto(self, *linhas:str):
        #Versão simples para o card 'Normais'.
        for w in self._scroll.winfo_children():
            w.destroy()
        for linha in linhas:
             ctk.CTkLabel(self._scroll, text=linha,
                          text_color="#3d3d3a",
                          font=ctk.CTkFont(size=11),
                          anchor="w").pack(fill="x", pady=2)