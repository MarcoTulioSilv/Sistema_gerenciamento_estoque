"""
gui · telas · t10_posicao_estoque.py
Tela T-10 — Posição atual do estoque por lote — todos os perfis (UC-07).
Exibe produto, lote, nota fiscal, saldo, vencimento e situação.
Ações de Entrada/Retirada disponíveis apenas para Técnico.
"""
import logging
import customtkinter as ctk

from Modulo_02_estoque import EstoqueService
from gui.componentes.form_widgets import FeedbackBanner
from gui.componentes.tabela_scroll import TabelaScroll

logger= logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM,
)

_SITUACAO_COR = {
    "Vencido":       ("#FCEBEB", "#A32D2D"),
    "Vence em 7d":   ("#FCEBEB", "#A32D2D"),
    "Vence em 15d":   ("#FAEEDA", "#854F0B"),
    "Vence em 30d":  ("#FAEEDA", "#854F0B"),
    "Normal":        ("#EAF3DE", "#27500A"),
    "Uso Contínuo":   ("#EAF3DE", "#27500A"),
}

_COLUNAS = [
    ("Produto",     200),
    ("Lote",         150),
    ("Nota Fiscal",  100),
    ("Centro",       100),
    ("Unidade de estoque", 100),
    ("Qtd atual",    80),
    ("Vencimento",  100),
    ("Situação",    120),
    ("Ações",       150),
]


_SITUACAO_LABEL = {
    "uso_continuo": "Uso Contínuo",
    "vencido":      "Vencido",
    "vence_7d":     "Vence em 7d",
    "vence_15d":    "Vence em 15d",
    "vence_30d":    "Vence em 30d",
    "normal":       "Normal",
    }

class TelaPosicaoEstoque(ctk.CTkFrame):
    #posição atual do estoque por lote- somente leitura para TI, com ações para administração e Tecnico
    def __init__(self, master, usuario, on_navigate, produto_id:int=None):
        super().__init__(master,fg_color=COR_CINZA_E,corner_radius=0)
        self._usuario = usuario
        self._on_navigate= on_navigate
        self._produto_id= produto_id
        self._linhas= [] #(lote, produto, situacao)
        self.permissao= usuario.perfil.value in ("tecnico", "admin", "ti")
        self._timer_busca= None
        self._pagina_atual = 0          
        self._itens_por_pagina = 30 # Lotes ocupam menos espaço visual, podemos renderizar 30 por vez
        self._lista_filtrada_atual = [] 
        self._carregando_pagina = False 
        self._timer_scroll = None
        self._construir()
        self._carregar()
        self._monitorar_scroll()

    #___ Construçãp_________________________________________________________________________________________
    def _construir(self):
        self._topbar=ctk.CTkFrame(self,fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text="Estado atual do estoque",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(self._topbar, text="atualizar", width=90, height=28,
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
        self._entry_busca.bind("<KeyRelease>",self._agendar_filtro)

        self._opt_centro= ctk.CTkOptionMenu(
            filt, values=["Todos os centros", "Almoxarifado", "Farmacia","Deposito"],
            width=150, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color= COR_AZUL_M, text_color="#161614",
            command=lambda _: self._filtrar())
        self._opt_centro.pack(side="left", padx=8)

        self._opt_situacao= ctk.CTkOptionMenu(
            filt,
            values=["Todas as situações", "Normal", 
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
        
        self._banner= FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)
        
        # Tabela: cabeçalho (row 0) e linhas de dados (row 1+) compartilham a
        # MESMA grade (self._tabela.grade) — garante alinhamento de coluna
        # de verdade, e dá scroll vertical + horizontal juntos (ver
        # gui/componentes/tabela_scroll.py).
        self._tabela = TabelaScroll(self, fg_color_grade=COR_BRANCO,
                                    border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        self._tabela.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        grade = self._tabela.grade
        for col, (txt, largura) in enumerate(_COLUNAS):
            grade.grid_columnconfigure(col, minsize=largura)
        grade.grid_columnconfigure(0, weight=1)  # Produto — absorve o espaço sobrando

        for col, (txt, largura) in enumerate(_COLUNAS):
            ancora = "center" if col !=0 else "w"
            celula = ctk.CTkFrame(grade, fg_color="#FFFFFF", corner_radius=0)
            celula.grid(row=0, column=col, sticky="nsew")
            ctk.CTkLabel(celula, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=9, weight="bold"),
                         anchor=ancora
                         ).pack(fill="x", expand=True, padx=6, pady=5)

        self._lbl_rodape= ctk.CTkLabel(
            self, text="", text_color="#888780", font=ctk.CTkFont(size=10))
        self._lbl_rodape.pack(anchor="w", padx=18, pady=(0,8))
    
    
    #___________Dados___________________________________________________________________
    def _carregar(self):
        try:
            nome_produto_filtro = ""
            if self._produto_id:
                produto_ref = EstoqueService.buscar_produto_por_id(self._produto_id)
                if produto_ref:
                    nome_produto_filtro = produto_ref.nome

            lotes = EstoqueService.listar_situacao_lotes(produto_id=self._produto_id)
            # apenas_com_saldo=True (padrão) já exclui lotes esgotados na origem.
            self._linhas = [
                (dto, _SITUACAO_LABEL.get(dto.situacao, "Normal"))
                for dto in lotes
            ]

        except Exception as exc:
            logger.error("Erro ao carregar posição estoque: %s", exc)
            self._banner.erro(str(exc))
            return
        
        if nome_produto_filtro:
            self._entry_busca.delete(0, "end")
            self._entry_busca.insert(0, nome_produto_filtro)

        self._filtrar()
    
    def _filtrar(self):
        busca = self._entry_busca.get().lower().strip()
        centro = self._opt_centro.get()
        situacao = self._opt_situacao.get()

        filtrados = []
        for dto, s in self._linhas:
            try:
                nome_prod = dto.produto_nome.lower() if dto.produto_nome else ""
                num_lote = dto.num_lote.lower() if dto.num_lote else ""
                nf_segura = dto.nota_fiscal.lower() if dto.nota_fiscal else ""

                centro_val = ""
                if dto.centro_alocacao:
                    centro_val = str(getattr(dto.centro_alocacao, 'value', dto.centro_alocacao)).lower()

                nome_ok = (busca in nome_prod or busca in num_lote or busca in nf_segura)
                centro_ok = (centro == "Todos os centros" or centro_val in centro.lower())
                situacao_ok = (situacao == "Todas as situações" or s == situacao)

                if nome_ok and centro_ok and situacao_ok:
                    filtrados.append((dto, s))

            except Exception as e:
                logger.error(f"Falha ao filtrar o lote {getattr(dto, 'lote_id', 'Desconhecido')}: {e}")
                continue
                
        # --- ATIVA A PAGINAÇÃO ---
        self._lista_filtrada_atual = filtrados
        self._pagina_atual = 0
        self._tabela.limpar_linhas(a_partir_da_row=1)
        self._renderizar_proxima_pagina()

    def _renderizar_proxima_pagina(self):
        self._carregando_pagina = True

        inicio = self._pagina_atual * self._itens_por_pagina
        fim = inicio + self._itens_por_pagina

        lote_linhas = self._lista_filtrada_atual[inicio:fim]
        self._renderizar(lote_linhas, inicio)

        self._pagina_atual += 1
        self.after(100, lambda: setattr(self, '_carregando_pagina', False))

    def _monitorar_scroll(self):
        inicio_proxima = self._pagina_atual * self._itens_por_pagina

        if not self._carregando_pagina and inicio_proxima < len(self._lista_filtrada_atual):
            try:
                _, bottom = self._tabela._canvas.yview()
                if bottom >= 0.95:
                    self._renderizar_proxima_pagina()
            except Exception:
                pass
            
        self._timer_scroll = self.after(200, self._monitorar_scroll)

    def _limpar_filtros(self):
        busca = self._entry_busca.get().strip()
        centro = self._opt_centro.get()
        situacao = self._opt_situacao.get()

        if not busca and centro == "Todos os centros" and situacao == "Todas as situações":
            return

        self._entry_busca.delete(0, "end")
        self._opt_centro.set("Todos os centros")
        self._opt_situacao.set("Todas as situações")
        self._filtrar()

    def _renderizar(self, linhas, indice_inicial: int):
        grade = self._tabela.grade

        if not linhas and indice_inicial == 0:
            ctk.CTkLabel(grade, text="Nenhum lote encontrado.",
                        text_color=COR_VERM,
                        font= ctk.CTkFont(size=12)
                        ).grid(row=1, column=0, columnspan=len(_COLUNAS), pady=24)
            self._lbl_rodape.configure(text="")
            return

        for offset, (dto, situacao) in enumerate(linhas):
            i = indice_inicial + offset
            row_idx = i + 1  # row 0 é o cabeçalho, na mesma grade
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E

            lote_str= dto.num_lote if dto.num_lote else"S/L"
            venc_str = dto.data_vencimento.strftime("%d/%m/%Y") if dto.data_vencimento else "—"

            valores = [
                dto.produto_nome,
                lote_str,
                dto.nota_fiscal or "S/N",
                dto.centro_alocacao.value.capitalize(),
                dto.unidade_estoque.value.capitalize(),
                str(dto.quantidade_atual),
                venc_str
            ]

            for col, val in enumerate(valores):
                ancora = "w" if col <= 3 else "center"
                ctk.CTkLabel(grade, text=val, text_color="#3d3d3a", fg_color=bg,
                             font=ctk.CTkFont(size=11), anchor=ancora, corner_radius= 5,
                             ).grid(row=row_idx, column=col, padx=6, pady=4, sticky="nsew")

            # Badge situação
            fg_s, tc_s = _SITUACAO_COR.get(situacao, ("#F1EFE8", "#5F5E5A"))
            wrap_situacao = ctk.CTkFrame(grade, fg_color="transparent", corner_radius=0)
            wrap_situacao.grid(row=row_idx, column=7, padx=6, pady=6, sticky="nsew")
            ctk.CTkLabel(wrap_situacao, text=situacao,
                         fg_color=fg_s, text_color=tc_s,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         corner_radius=6, padx=6, pady=2).pack()

            #Ações — alinhadas à direita, fundo zebrado preenchendo a célula
            wrap_acoes = ctk.CTkFrame(grade, fg_color="transparent", corner_radius=0)
            wrap_acoes.grid(row=row_idx, column=8, padx=6, pady=4, sticky="nsew")

            if self.permissao:
                acoes = ctk.CTkFrame(wrap_acoes, fg_color="transparent")
                acoes.pack(side="right")

                pid = dto.produto_id
                ctk.CTkButton(
                    acoes, text="Entrada", width=64, height=26,
                    fg_color=COR_BRANCO, text_color="#3d3d3a",
                    border_width=1, border_color=COR_CINZA_B,
                    hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                    command=lambda p=pid: self._on_navigate("entrada_manual", extra=p)
                ).pack(side="left", padx=(0,4))

                  #Retirada bloqueada para lotes vencidos
                pode_retirar = situacao != "Vencido"
                centro_val = dto.centro_alocacao.value
                ctk.CTkButton(
                    acoes, text="Retirada", width=64, height=26,
                    fg_color=COR_BRANCO, text_color="#3d3d3a" if pode_retirar else "#AAAAAA",
                    border_width=1, border_color=COR_CINZA_B,
                    hover_color=COR_CINZA_E if pode_retirar else COR_BRANCO,
                    font=ctk.CTkFont(size=11),
                    state="normal" if pode_retirar else "disabled",
                    command=(lambda p=pid, c=centro_val: self._on_navigate("retirada", extra={"produto_id": p, "centro_origem": c}))
                    if pode_retirar else None,
                ).pack(side="left")

        total_encontrado = len(self._lista_filtrada_atual)
        vencidos = sum(1 for _, s in self._lista_filtrada_atual if s == "Vencido")
        self._lbl_rodape.configure(
            text=f"{total_encontrado} lote(s) exibidos" + (f". {vencidos} vencidos" if vencidos else "")
        )

    def _erro_na_tela(self, detalhe:str):
        self._tabela.limpar_linhas(a_partir_da_row=1)
        ctk.CTkLabel(self._tabela.grade,
                     text=f"Erro ao carregar estoque: \n {detalhe}",
                     text_color= COR_VERM, font=ctk.CTkFont(size=12),
                     wraplength=600, justify="left"
                     ).grid(row=1, column=0, columnspan=len(_COLUNAS), pady=24, padx=16)
    
    def limpar_memoria(self):
        """Método chamado pelo app.py ao sair da tela para esvaziar a RAM."""
        if hasattr(self, '_linhas') and self._linhas is not None:
            self._linhas.clear()
            self._linhas = None
            
        if self._timer_scroll is not None:
            self.after_cancel(self._timer_scroll)
            self._timer_scroll = None

    def _agendar_filtro(self, event=None):
        #timer para usuario digitar 
        if self._timer_busca is not None:
            self.after_cancel(self._timer_busca)

        self._timer_busca = self.after(400, self._filtrar)