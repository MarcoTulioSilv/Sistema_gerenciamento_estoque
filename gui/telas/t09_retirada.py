"""
gui.telas. t09_retirada.py
Tela t-09- Registro de retirada multi-lote FEFO
(UC-06, RF-07, RF-09, RN-08)
"""

import logging 
from decimal import InvalidOperation

import customtkinter as ctk
from tkinter import messagebox
from gui.componentes.form_widgets import(   Campo, CampoBarras, BotoesFormulario, SecaoFormulario, FeedbackBanner)
from Modulo_02_estoque import EstoqueService, LoteRepo, ProdutoRepo
from datetime import date

logger= logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERDE_BG = "#E1F5EE"
COR_VERDE_T  = "#0F6E56"
COR_VERM   = "#A32D2D"
COR_AMBER  = "#BA7517"

class TelaRetirada(ctk.CTkFrame):
    #Registro de retirada com plano FEFO multi-lote exibido antes da confirmação.

    def __init__(self, master, usuario,on_navigate, produto_id: int=None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario= usuario
        self._on_navigate= on_navigate
        self._produto_sel= None
        self._plano= None
        self._construir()   
        if produto_id:
            self._buscar_produto_por_id(produto_id)

    #_________ Construção______________________________________________________________
    def _construir(self):
        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44,corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Registro de retirada",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        self._banner= FeedbackBanner(self)
        self._banner.pack(fill="x",padx=16, pady=(8,0))

        scroll= ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both",expand=True)
        #___ Seção 1: Identificar produto________________________________________________
        sec1= SecaoFormulario(scroll, titulo="Identificar produto")
        sec1.pack(fill="x", padx=16, pady=(12,0))

        row_id=ctk.CTkFrame(sec1, fg_color="transparent")
        row_id.pack(fill="x", padx=14, pady=(0,8))
        row_id.grid_columnconfigure(0,weight=2)
        row_id.grid_columnconfigure(1,weight=2)

        self._campo_ean= CampoBarras(
            row_id, label="Codigo de barras(EAN)",
            on_leitura= self._ao_ler_ean)
        self._campo_ean.grid(row=0,column=0, padx=(0,12), sticky="ew")
        self._campo_qtd= Campo(row_id, "Quantidade a retirar",
                               obrigatorio=True, tipo="number", placeholder="0")
        self._campo_qtd.grid(row=0, column=1, sticky="ew")
        self._campo_qtd._widget.bind("<Return>", lambda e: self._calcular_plano())


        #Card produto encontrado
        self._frame_produto= ctk.CTkFrame(sec1, fg_color=COR_VERDE_BG,
                                          corner_radius=6, border_width=1, 
                                          border_color="#97C459")
        self._lbl_produto= ctk.CTkLabel(
            self._frame_produto,text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), justify="left", anchor="w")
        self._lbl_produto.pack(fill="x", padx=12, pady=8)

        ctk.CTkButton(sec1, text="Calcular plano de retirada ->",
                      width=180, height=32,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      font=ctk.CTkFont(size=12),
                      command= self._calcular_plano).pack(anchor="w", padx=14, pady=(0,12)) 
        
        
        #____ Seção 2: Plano de consumo
        self._sec2= SecaoFormulario(scroll, titulo= "Plano de Consumo")
        #Oculto até plano calculado

        self._frame_plano=ctk.CTkFrame(self._sec2, fg_color=COR_CINZA_E,
                                       corner_radius=6)
        self._frame_plano.pack(fill="x", padx=14, pady=(0,8))

        #Aviso de estoque insuficiente
        self._frame_insuf=ctk.CTkFrame(
            sec1, fg_color="#FCEBEB", corner_radius=6,
            border_width=1, border_color="#F09595")
        self._lbl_insuf=ctk.CTkLabel(
            self._frame_insuf, text="", text_color=COR_VERM,
            font=ctk.CTkFont(size=12), justify="left")
        self._lbl_insuf.pack(fill="x", padx=12, pady=8)

        #___ Seção 3: Observações
        self._sec3=SecaoFormulario(scroll, titulo="Observações")
        self._campo_obs=ctk.CTkEntry(
            self._sec3,
            placeholder_text="Ex: Retirada para enfermaria 2- Dr. silva",
            height=34, corner_radius=6 )
        self._campo_obs.pack(fill="x", padx=14, pady=(0,6))
        ctk.CTkLabel(self._sec3,
                     text="Quando preenchido, aparece em todos os registros desta retirada.",
                     text_color="#888780", font=ctk.CTkFont(size=10)
        ).pack(anchor="w", padx=0, pady=(0,12))

        #______Botões

        self._row_btns= ctk.CTkFrame(scroll,fg_color="transparent")
        self._btn_confirmar= ctk.CTkButton(
            self._row_btns, text="Confirmar retirada",
            width=180, height=36, 
            fg_color="#1D9E75", hover_color="#0F6E56",
            state="disabled",
            command=self._confirmar)
        ctk.CTkButton(self._row_btns, text="Cancelar",
                      width=100, height=36,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=lambda:self._on_navigate("produtos")
                      ).pack(side="left", padx=(0,8))
        self._btn_confirmar.pack(side="left")

        self._campo_ean.focus()
    
    # ___ Produto____________________________________________________________
    def _ao_ler_ean(self, ean:str):
        try:
            produto= EstoqueService.buscar_produto_por_ean(ean)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto:{exc}")
            return
        
        if produto is None:
            self._campo_ean.erro(f"EAN'{ean}' não cadastrado.")
            self._frame_produto.pack_forget()
            self._produto_sel=None
            return
        
        lotes= LoteRepo.listar_por_produto(produto.id)
        saldo= sum(l.quantidade_atual for l in lotes
                   if l.data_vencimento>= date.today())
        
        self._campo_ean.erro("")
        self._produto_sel= produto
        self._lbl_produto.configure(
            text=(f"{produto.nome}\n"
                  f"Centro de alocação: {produto.centro_alocacao.value.capitalize()}.\n"
                  f"Saldo total disponivel: {saldo} unid. em "
                  f"{len([l for l in lotes if l.quantidade_atual>0])} lote(s)")
        )
        self._frame_produto.pack(fill="x", padx=14, pady=(0,8))
        self._plano= None
        self._sec2.pack_forget()
        self._btn_confirmar.configure(state="disabled")
        self._row_btns.pack_forget()
    
    def _buscar_produto_por_id(self, produto_id: int):
        try:
            p= ProdutoRepo.buscar_por_id(produto_id)
            if p:
                self._campo_ean.set(p.ean)
                self._ao_ler_ean(p.ean)
        except Exception as exc:
            logger.error("Erro ao pré-selecionar produto: %s", exc)

    #______Plano FEFO_______________________________________________________________________

    def _calcular_plano(self):
        if not self._produto_sel:
            self._banner.erro("Leia ou digite o código do produto primeiro")
            return
        try:
            qtd= int(self._campo_qtd.get())
            if qtd<=0  :
                raise ValueError()
        except ValueError:
            self._campo_qtd.erro("Informe um número inteiro maior que zero.")
            return
        self._campo_qtd.erro("")

        try:
            plano= EstoqueService.calcular_plano_fefo(self._produto_sel.id, qtd)
            if not plano.atendido_completo:
                #RF-09- estoque insuficiente 
                self._lbl_insuf.configure(
                    text=(f"Estoque insufiente para {plano.quantidade_pedida} unidade(s).\n"
                        f"Quantidade máxima disponível: {plano.quantidade_maxima_disponivel} unid.")
                )
                self._frame_insuf.pack(fill="x", padx=14, pady=(0,8))
                self._btn_confirmar.configure(state="disabled")
                return
            
            self._frame_insuf.pack_forget()
        except Exception as exc:
            self._banner.erro(f"Erro ao calcular plano: {exc}")
            logger.error("erro ao calcular plano:%s",exc)
            return
            

        self._plano= plano
        self._exibir_plano(plano)

    def _exibir_plano(self, plano):
        #Limpar frame do plano
        for w in self._frame_plano.winfo_children():
            w.destroy()

        # Cabeçalho do plano
        ctk.CTkLabel(
            self._frame_plano,
            text=(f"Serão retiradas{plano.quantidade_pedida} unidade(s)"
                  f"de {len(plano.itens)} lote(s):"),
                  font=ctk.CTkFont(size=12, weight="bold"),
                  text_color=COR_AZUL, anchor="w"
        ).pack(fill="x", padx=10, pady=(8,6))

        # linhas por lote
        for item in plano.itens:
            linha = ctk.CTkFrame(self._frame_plano, fg_color=COR_BRANCO,
                                 corner_radius=6, border_width=1,
                                 border_color=COR_CINZA_B)
            linha.pack(fill="x",padx=10,pady=3)

            ctk.CTkLabel(
                linha,
                text=f" Lote {item.num_lote}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COR_AZUL, anchor="w" ,width= 160
            ).grid(row=0, column=8, padx=8, sticky="w")

            ctk.CTkLabel(
                linha,
                text=f"Vence: {item.data_vencimento.strftime('%d/%m/%Y')}",
                text_color="#888780", font=ctk.CTkFont(size=11),
                anchor="w", width=160
            ).grid(row=0,column=1, padx=8,sticky="w")

            ctk.CTkLabel(
                linha,
                text=f"NF:{item.nota_fiscal}",
                text_color="#888780", font=ctk.CTkFont(size=11),
                anchor="w", width=130
            ).grid(row=0, column=2, padx=8, pady=8, sticky="w")

            ctk.CTkLabel(
                linha,
                text=f"Atual:{item.saldo_atual}",
                text_color="#3d3d3a", font=ctk.CTkFont(size=11),
                anchor="w", width=120
            ).grid(row=0,column=3, padx=8, pady=8, sticky="w")

            ctk.CTkLabel(
                linha,
                text=f"Retirar: {item.qtd_a_retirar}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COR_AZUL_M, anchor="w", width=100
            ).grid(row=0,column=4,padx=8,pady=8, sticky="w")

            cor_saldo= COR_VERM if item.lote_esgotado else COR_VERDE_T

            saldo_txt="0- lote esgotado" if item.lote_esgotado else str(item.saldo_restante)
            ctk.CTkLabel(
                linha,
                text=f"Saldo restante: {saldo_txt}",
                font=ctk.CTkFont(size=11),
                text_color=cor_saldo, anchor="w", width=180
            ).grid(row=0, column=5,padx=8,pady=8, sticky="w")

            ctk.CTkLabel(
                self._frame_plano,
                text="Confirme o plano abaixo para registrar a retirada.",
                text_color="#5F5E5A", font=ctk.CTkFont(size=11), anchor="w"
            ).pack(fill="x", padx=10, pady=(4,8))
            
            self._sec2.pack(fill="x", padx=16,pady=(10,0))
            self._sec3.pack(fill="x", padx=16,pady=(10,0))
            self._btn_confirmar.configure(state="normal")
            self._row_btns.pack(anchor="e", padx=16, pady=(0,16))

    #_____ Confirmar_______________________________________________________________________________

    def _confirmar(self):
        if not self._plano:
            return
        obs= self._campo_obs.get().strip() or None
        try:
            estoque_baixo= EstoqueService.registrar_retirada(
                self._plano, self._usuario.id, obs)
            msg=(f"Retirada registrada:{self._plano.quantidade_pedida} unid."
                 f" de '{self._produto_sel.nome}'.")
            if estoque_baixo:
                msg += "\n Estoque abaixo do mínimo- alerta enviado."
                self._banner.sucesso(msg)
                self._limpar()
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao registrar retirada: %s", exc)
            self._banner.erro(f"Erro ao registrar:{exc}")
    
    def _limpar(self):
        self._produto_sel = None
        self._plano       = None
        self._campo_ean.limpar()
        self._campo_qtd.limpar()
        self._campo_obs.delete(0, "end")
        self._frame_produto.pack_forget()
        self._sec2.pack_forget()
        self._sec3.pack_forget()
        self._row_btns.pack_forget()
        self._btn_confirmar.configure(state="disabled")
        self._campo_ean.focus()