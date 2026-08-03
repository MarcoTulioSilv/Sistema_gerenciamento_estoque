"""
gui.telas.t02_inicio.py
Tela T-02 - Painel de situação (KPIs de estoque, lotes vencidos/a vencer).
"""

import logging
from datetime import date, datetime
import customtkinter as ctk

from Modulo_02_estoque import EstoqueService

logger= logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_AZUL_L, COR_CINZA_E, COR_CINZA_B,
    COR_VERDE, COR_AMBER, COR_VERM, COR_BRANCO,
)

def _consultar_kpis()->dict:
    """
    Consulta os KPIs de situação de estoque via EstoqueService.
    Retorna dicionário com contagens para exibição nos cards.
    """
    hoje= date.today()
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
        # Saldo via vw_saldo_produtos: exclui vencidos ainda não retirados,
        # inclui lotes "de consumo" sem data_vencimento (soma feita no banco).
        produtos_ativos = [p for p in EstoqueService.listar_view_produtos() if p.ativo]
        kpis["produtos_ativos"] = len(produtos_ativos)

        # Estoque abaixo do mínimo (produtos ativos)
        for prod in produtos_ativos:
            if prod.estoque_minimo <= 0:
                continue
            saldo = int(prod.saldo_total) if prod.saldo_total is not None else 0
            if saldo <= prod.estoque_minimo:
                kpis["estoque_baixo"] += 1

        # Lotes vencidos / vencendo em até 15 dias (cross-produto)
        for l in EstoqueService.listar_situacao_lotes():
            if l.data_vencimento is None:
                continue
            detalhe = f"• {l.produto_nome} (Lote: {l.num_lote}) - Vence em: {l.data_vencimento.strftime('%d/%m/%Y')}"
            if l.situacao == "vencido":
                kpis["lotes_vencidos"] += 1
                kpis["nomes_vencidos"].append(detalhe)
            elif l.situacao in ("vence_7d", "vence_15d"):
                kpis["lotes_vencendo_15"] += 1
                kpis["nomes_vencendo_15"].append(detalhe)

        # Movimentações do dia
        inicio_hoje= datetime.combine(hoje,datetime.min.time())
        kpis["mov_hoje"] = EstoqueService.contar_movimentacoes_desde(inicio_hoje)
    except Exception as exc:
        logger.error("Erro ao consultar KPIs:%s",exc)
    return kpis

class TelaInicio(ctk.CTkFrame):
    """Tela inicial com KPIs e Painel de alertas- UC-07, UC-17,RF-22."""

    REFRESH_MS=120_000 # atualiza KPIs a cada 2 minutos

    def __init__(self,master,usuario, on_navigate=None):
        super().__init__(master,fg_color=COR_CINZA_E,corner_radius=0)
        self._usuario = usuario
        self._timer   = None
        self._on_navigate = on_navigate
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

    def _abrir_baixa_vencidos(self):
        """Busca os lotes vencidos de forma estruturada e os envia para a tela de retirada"""
        lotes_vencidos_raw = []

        try:
            for l in EstoqueService.listar_situacao_lotes():
                if l.situacao == "vencido":
                    lotes_vencidos_raw.append({
                        "ean": l.produto_ean,
                        "lote": l.num_lote,
                        "quantidade": l.quantidade_atual,
                        "nome": l.produto_nome,
                    })
        except Exception as exc:
            logger.error("Erro ao buscar lotes vencidos para a fila de baixa: %s", exc)

        # Encaminha o destino junto com a lista estruturada de lotes no argumento extra
        self._on_navigate("baixa_vencido", lotes_vencidos_raw)
    
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
        """Abre uma janela customizada com os detalhes dos lotes vencidos e opção de baixa"""
        if not hasattr(self, '_lista_vencidos') or not self._lista_vencidos:
            return

        detalhes = "\n".join(self._lista_vencidos)
        
        # 1. Cria a janela customizada (Toplevel)
        popup = ctk.CTkToplevel(self)
        popup.title("Atenção - Lotes Vencidos")
        popup.geometry("550x400")
        popup.transient(self) # Mantém a janela sempre à frente da principal
        popup.grab_set()      # Torna a janela modal (bloqueia cliques fora dela)
        
        # 2. Título interno
        ctk.CTkLabel(
            popup, 
            text="Os seguintes lotes já passaram da data de validade:", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#A32D2D" # COR_VERM
        ).pack(pady=(20, 10), padx=20, anchor="w")
        
        # 3. Caixa de texto com scroll (melhor para listas extensas)
        txt_box = ctk.CTkTextbox(popup, width=510, height=200, fg_color="#F2F1ED")
        txt_box.pack(pady=10, padx=20, fill="both", expand=True)
        txt_box.insert("1.0", f"{detalhes}\n\nFavor realizar a retirada de estoque.")
        txt_box.configure(state="disabled") # Bloqueia edição pelo usuário
        
        # 4. Frame para organizar os botões no rodapé
        frame_botoes = ctk.CTkFrame(popup, fg_color="transparent")
        frame_botoes.pack(pady=20, fill="x", side="bottom")
        
        # Botão Fechar (Cancela a ação)
        ctk.CTkButton(
            frame_botoes, 
            text="Fechar", 
            width=100, height=32,
            fg_color="transparent", 
            border_width=1,
            text_color="#3d3d3a",
            command=popup.destroy
        ).pack(side="right", padx=20)
        
        # Função auxiliar: fecha o popup e chama a sua função original
        def _acao_dar_baixa():
            popup.destroy()
            self._abrir_baixa_vencidos()
            
        # Botão Dar baixa
        ctk.CTkButton(
            frame_botoes, 
            text="Dar baixa", 
            width=120, height=32,
            fg_color="#A32D2D", # COR_VERM
            hover_color="#7a1f1f",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=_acao_dar_baixa
        ).pack(side="right", padx=(0, 10))

    def destroy(self):
        """Cancela o timer ao destruir tela"""
        if self._timer:
            self.after_cancel(self._timer)
        super().destroy()

    def limpar_memoria(self):
        """Para o timer de auto-refresh e limpa a lista de vencidos."""
        if hasattr(self, '_timer') and self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
            
        if hasattr(self, '_lista_vencidos') and self._lista_vencidos is not None:
            self._lista_vencidos.clear()
            self._lista_vencidos = None