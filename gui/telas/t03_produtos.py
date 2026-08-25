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

from gui.componentes.tabela_scroll import TabelaScroll

logger= logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_AZUL_L, COR_CINZA_E, COR_CINZA_B,
    COR_BRANCO, COR_VERDE, COR_AMBER, COR_VERM,
)

_STATUS_COR={
     "Ativo":          ("#EAF3DE", "#27500A"),
    "Inativo":        ("#F1EFE8", "#5F5E5A"),
    "Estoque baixo":  ("#FAEEDA", "#854F0B"),
}

# Colunas: (header, largura)
_COLUNAS = [
    ("Nome",      300),
    ("EAN ",       150),
    ("Marca ",     150),
    ("Fornecedor ", 150),
    ("Est.mín.",   80),
    ("Saldo ",      80),
    ("Status",    100),
    ("Ações",     100),
]

class TelaProdutos(ctk.CTkFrame):
    """Listagem de produtos com filtros e ações de navegação"""

    def __init__(self, master, usuario,on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._produtos    = []
        self._timer_busca= None
        self._pagina_atual = 0          
        self._itens_por_pagina = 20     
        self._lista_filtrada_atual = [] 
        self._carregando_pagina = False 
        self._timer_scroll = None
        self._construir()
        self._carregar_todos()
        self._monitorar_scroll()

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

        self._entry_busca= ctk.CTkEntry(filt, placeholder_text="Buscar por nome, EAN ou Fornecedor...",
                                    height=32, width= 300, corner_radius=6)
        self._entry_busca.pack(side="left", padx=(0,8))
        self._entry_busca.bind("<KeyRelease>", self._agendar_filtro)

        self._opt_lista= ctk.CTkOptionMenu( 
            filt,
            values=["Todas as situações", "Somente ativos", "Somente inativos", "Estoque baixo"],
            width=170, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#161614",
            command=self._filtrar)
        self._opt_lista.pack(side="left", padx=(0,8))

        ctk.CTkButton(filt, text="Limpar", width=70, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color= COR_CINZA_B,
                      hover_color= COR_CINZA_E,
                      command= self._limpar_filtros).pack(side="left")


        # Tabela: cabeçalho (row 0) e linhas de dados (row 1+) compartilham a
        # MESMA grade (self._tabela.grade) — garante alinhamento de coluna
        # de verdade, e dá scroll vertical + horizontal juntos (ver
        # gui/componentes/tabela_scroll.py).
        self._tabela = TabelaScroll(self, fg_color_grade=COR_BRANCO,
                                    border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        self._tabela.pack(fill="both", expand=True, padx=16, pady=(10, 16))

        grade = self._tabela.grade
        for col, (txt, largura) in enumerate(_COLUNAS):
            grade.grid_columnconfigure(col, minsize=largura)
        grade.grid_columnconfigure(0, weight=1)  # Nome — absorve o espaço sobrando

        for col, (txt, largura) in enumerate(_COLUNAS):
            ancora = "w" if col == 0 else "center"

            celula = ctk.CTkFrame(grade, fg_color="#FAFAF8", corner_radius=0)
            celula.grid(row=0, column=col, sticky="nsew")

            ctk.CTkLabel(celula, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         anchor=ancora
                         ).pack(side="left", fill="x", expand=True, padx=8, pady=6)

            # Injeta a barra de divisão de 1px à direita (exceto na última coluna)
            if col < len(_COLUNAS) - 1:
                divisor = ctk.CTkFrame(celula, width=1, height=18, fg_color=COR_CINZA_B)
                divisor.pack_propagate(False) # Impede que a barra mude de tamanho
                divisor.pack(side="right", pady=6)

    def _carregar_todos(self):
        self._dados_completos = []
        try:
            produtos_view = EstoqueService.listar_view_produtos()
            
            for p in produtos_view:
                saldo = int(p.saldo_total) if p.saldo_total is not None else 0
                
                ativo = bool(p.ativo)
                
                if not ativo:
                    status = "Inativo"
                elif p.estoque_minimo > 0 and saldo <= p.estoque_minimo:
                    status = "Estoque baixo"
                else:
                    status = "Ativo"
                
                self._dados_completos.append((p, saldo, status))
                
        except Exception as exc:
            logger.error("Erro ao carregar produtos pela View: %s", exc)
            self._dados_completos = []

        # Aplica os filtros padrão e aciona a paginação para desenhar a tela
        self._filtrar()
    def _filtrar(self, event=None):
        """Filtra apenas na memória (super rápido), sem ir ao banco de dados."""
        busca = self._entry_busca.get().lower().strip()
        filtro_selecionado = self._opt_lista.get()

        filtrados = []
        for p, saldo, status in self._dados_completos:
            nome_seguro = p.nome.lower() if p.nome else ""
            ean_seguro  = p.ean.lower() if p.ean else ""
            fornecedor_seguro = p.fornecedor.lower() if p.fornecedor else ""
            # 1. Filtro de Texto
            nome_ok = busca in nome_seguro or busca in ean_seguro or  busca in fornecedor_seguro
    
            # 2. Filtro de Situação 
            status_ok = True
            if filtro_selecionado == "Somente ativos":
                status_ok = p.ativo is True
            elif filtro_selecionado == "Somente inativos":
                status_ok = p.ativo is False
            elif filtro_selecionado == "Estoque baixo":
                status_ok = status == "Estoque baixo"

            # Se atendeu as duas condições, adiciona na lista da tela
            if nome_ok and status_ok:
                filtrados.append((p, saldo, status))
            
        self._lista_filtrada_atual = filtrados  # Guarda a lista completa
        self._pagina_atual = 0
        self._tabela.limpar_linhas(a_partir_da_row=1)
        self._renderizar_proxima_pagina()

    def _limpar_filtros(self):
        busca = self._entry_busca.get().strip()
        situacao = self._opt_lista.get()

        # 1. VALIDAÇÃO DE ESTADO: Se já está tudo limpo, aborta a função silenciosamente!
        if not busca and situacao == "Todas as situações":
            return

        self._entry_busca.delete(0, "end")
        self._opt_lista.set("Todas as situações") # Corrigido a letra maiúscula aqui para coincidir com a lista
        
        self._filtrar()

    def _limpar_filtros(self):
        self._entry_busca.delete(0, "end")
        self._opt_lista.set("Todas as situações")
        self._filtrar()
    
    def _renderizar(self, lista_produtos, indice_inicial: int):
        """Apenas desenha os componentes visuais, sem processamento de dados."""
        grade = self._tabela.grade

        if not lista_produtos and indice_inicial == 0:
            ctk.CTkLabel(grade, text="Nenhum produto encontrado.",
                         text_color="#888780", font=ctk.CTkFont(size=12)
                         ).grid(row=1, column=0, columnspan=len(_COLUNAS), pady=24)
            return

        for offset, (p, saldo, status) in enumerate(lista_produtos):
            i = indice_inicial + offset
            row_idx = i + 1  # row 0 é o cabeçalho, na mesma grade
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E

            valores = [
                p.nome,
                p.ean or "-",
                p.marca or "—",
                p.fornecedor or "-",
                str(p.estoque_minimo),
                str(saldo),
            ]

            for col, val in enumerate(valores):
                justifica = "center" if col in (4, 5) else "left"
                ctk.CTkEntry(grade, textvariable=tk.StringVar(value=val),
                             state="readonly", justify=justifica,
                             text_color="#3d3d3a", fg_color=bg, border_width=0,
                             font=ctk.CTkFont(size=12)
                             ).grid(row=row_idx, column=col, padx=8, pady=7, sticky="nsew")

            # --- STATUS VISUAL ---
            fg, tc = _STATUS_COR.get(status, ("#F1EFE8", "#5F5E5A"))
            wrap_status = ctk.CTkFrame(grade, fg_color="transparent", corner_radius=0)
            wrap_status.grid(row=row_idx, column=6, padx=8, pady=6, sticky="nsew")
            ctk.CTkLabel(wrap_status, text=status, fg_color=fg, text_color=tc,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         corner_radius=8, padx=8, pady=2).pack()

            # --- AÇÕES (alinhadas à direita, fundo zebrado preenchendo a célula) ---
            wrap_acoes = ctk.CTkFrame(grade, fg_color="transparent", corner_radius=0)
            wrap_acoes.grid(row=row_idx, column=7, padx=8, pady=4, sticky="nsew")
            botoes = ctk.CTkFrame(wrap_acoes, fg_color="transparent")
            botoes.pack(side="right")

            pid = p.id
            ctk.CTkButton(botoes, text="Editar", width=64, height=26,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                          font=ctk.CTkFont(size=11),
                          command=lambda p=pid: self._on_navigate("editar_produto", extra=p)
                          ).pack(side="left", padx=(0,4))

            ctk.CTkButton(botoes, text="Ver lotes", width=72, height=26,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                          font=ctk.CTkFont(size=11),
                          command=lambda p=pid: self._on_navigate("posicao", extra=p)
                          ).pack(side="left")

    def _renderizar_proxima_pagina(self):
        #avisa ao sistema que já estamos buscando dados para ele não duplicar
        self._carregando_pagina = True

        inicio = self._pagina_atual * self._itens_por_pagina
        fim = inicio + self._itens_por_pagina

        lote_produtos = self._lista_filtrada_atual[inicio:fim]
        self._renderizar(lote_produtos, inicio)

        self._pagina_atual += 1

        self.after(100, lambda: setattr(self, '_carregando_pagina', False))

    def _monitorar_scroll(self):
        """Monitora se a barra de rolagem chegou ao fim para carregar mais itens."""
        inicio_proxima = self._pagina_atual * self._itens_por_pagina
        
        if not self._carregando_pagina and inicio_proxima < len(self._lista_filtrada_atual):
            try:
                _, bottom = self._tabela._canvas.yview()

                if bottom >= 0.95:
                    self._renderizar_proxima_pagina()
            except Exception:
                pass
            
        self._timer_scroll = self.after(200, self._monitorar_scroll)

    def limpar_memoria(self):

        """Método chamado pelo app.py ao sair da tela para esvaziar a RAM."""
        # Limpa a lista principal de renderização
        if hasattr(self, '_dados_completos') and self._dados_completos is not None:
            self._dados_completos.clear()
            self._dados_completos = None
            
        # Limpa a lista secundária
        if hasattr(self, '_produtos') and self._produtos is not None:
            self._produtos.clear()
            self._produtos = None
        
        if self._timer_scroll is not None:
            self.after_cancel(self._timer_scroll)
            self._timer_scroll = None
    
    def _agendar_filtro(self, event=None):
        """Espera o usuário parar de digitar por 400ms antes de travar a tela renderizando."""
        # Se já existe uma contagem rodando (o usuário ainda está digitando), cancela!
        if self._timer_busca is not None:
            self.after_cancel(self._timer_busca)
            
        # Inicia um novo cronômetro de 400 milissegundos para disparar o filtro real
        self._timer_busca = self.after(400, self._filtrar)