"""
gui . telas . t07_entrada_manual.py
Tela T-07 - Registro de entrada manual (UC-03, UC-04, RF-02, RF-03, RN-07).
"""
import logging
from datetime import date,datetime
from decimal import Decimal, InvalidOperation

import customtkinter as ctk
from tkinter import messagebox
from gui.componentes.form_widgets import (Campo, CampoBarras, BotoesFormulario, SecaoFormulario, FeedbackBanner)
from Modulo_02_estoque import EstoqueService , ProdutoRepo, LoteRepo

logger= logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERDE  = "#EAF3DE"
COR_VERDE_T= "#27500A"

class TelaEntradaManual(ctk.CTkFrame):
    #Registro de entrada manual de produtos com criação de lote (UC-04).

    def __init__(self, master, usuario, on_navigate, produto_id: int=None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario    = usuario
        self._on_navigate = on_navigate
        self._produto_sel  = None # None = novo, int = edição
        self._construir()

        if produto_id:
            self._buscar_produto_por_id(produto_id)

    def _construir(self):
        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Entrada manual de produto",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)    
        ctk.CTkLabel(topbar, text="Início › Estoque › Entrada manual",
                     font= ctk.CTkFont(size=11), text_color="#888780"
                     ).pack(side="left", padx=4)
        
        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8,0))

        scroll= ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        #__ Passo 1: Identificar produto___________________________________________________
        sec1= SecaoFormulario(scroll,"1. Identificar produto")
        sec1.pack(fill="both", expand=True, padx=16, pady=8)

        self._ean= CampoBarras(sec1, on_leitura=self._on_leitura_ean )
        self._ean.pack(fill="x", padx=14, pady=(0,6))

        #Card de produto encontrado(oculto por padrão)
        self._card_produto= ctk.CTkFrame(sec1, fg_color=COR_VERDE, corner_radius=6,
                                        border_width=1, border_color="#97C459")
        self._lbl_produto= ctk.CTkLabel(
            self._card_produto, text="", text_color= COR_VERDE_T,
            font=ctk.CTkFont(size=12), anchor="w", justify="left",
        )
        self._lbl_produto.pack(anchor="w", padx=12, pady=8)

        self._btn_cadastrar= ctk.CTkButton(
            sec1, text= "Produto não encontrado- clique para cadastrar",
            fg_color="#FAEEDA", text_color="#854F0B",
            hover_color="#F7D9B9", height=34, corner_radius=6,
            command= lambda: self._on_navigate("novo_produto")
        )

        #__ Passo 2: Dados do lote____________________________________________________________________________
        self._sec2= SecaoFormulario(scroll,"2. Dados do lote")
        self._sec2.pack(fill="x", pady=(0,10))

        grid= ctk.CTkFrame(self._sec2, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0,8))
        grid.grid_columnconfigure((0,1,2), weight=1)

        self._num_lote= Campo(grid, "Número do lote", obrigatorio=True,
                              placeholder= "Digite o número do lote", )
        self._num_lote.grid(row=0, column=0, padx=10, pady=(0,12), sticky="ew")
        
        self._nota_fiscal= Campo(grid, "Número da nota fiscal", obrigatorio=True,
                                 placeholder="Digite o número da nota fiscal")
        self._nota_fiscal.grid(row=0, column=1, padx=10, pady=(0,12), sticky="ew")

        self._data_fab= Campo(grid, "Data de fabricação", 
                             placeholder="DD/MM/AAAA ou AAAA/MM/DD")
        self._data_fab.grid(row=0, column=2, sticky="ew")

        grid2= ctk.CTkFrame(self._sec2, fg_color="transparent")
        grid2.pack(fill="x", padx=14, pady=(0,8))
        grid2.grid_columnconfigure((0,1,2), weight=1)

        self._data_venc= Campo(grid2,"Data de vencimento", obrigatorio=True, placeholder="DD/MM/AAAA ou AAAA-MM-DD")
        self._data_venc.grid(row=0, column=0, padx=10, pady=(0,12), sticky="ew")

        self._quantidade= Campo(grid2, "Quantidade", tipo="number", obrigatorio=True, placeholder="0")
        self._quantidade.grid(row=0, column=1, padx=(0,12), sticky="ew")
        self._quantidade._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())

        self._valor_unit= Campo(grid2, "Valor unitário", tipo="number", obrigatorio=True, placeholder="0.00")
        self._valor_unit.grid(row=0, column=2, sticky="ew")
        self._valor_unit._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())

        # Valor total calculado
        self._lbl_total= ctk.CTkLabel(
            self._sec2, text="Valor total: -",
            text_color="#3d3d3a", font= ctk.CTkFont(size=12),
        )
        self._lbl_total.pack(anchor="w", padx=13, pady=(0,12))

        # Botões
        btns= BotoesFormulario(scroll, texto_salvar="Registrar entrada",
                               on_salvar=self._salvar,
                               on_cancelar= lambda: self._on_navigate("posicao"))
        btns.pack(anchor="e", pady=8)

    #Handlers

    def _on_leitura_ean(self, ean: str):
        self._produto_sel= EstoqueService.buscar_produto_por_ean(ean)
        self._card_produto.pack_forget()
        self._btn_cadastrar.pack_forget()

        if self._produto_sel:
            p = self._produto_sel
            self._lbl_produto.configure(
                text=f"{p.nome}\n"
                     f"Centro: {p.centro_alocacao.value.capitalize()} . "
                     f"Marca: {p.marca or '-'} ."
                     f"Estoque minimo: {p.estoque_minimo}"
            )
            self._card_produto.pack(fill="x", padx=14, pady=(0,12))
            self._num_lote.focus()
        else:
            self._btn_cadastrar.pack(fill="x", padx=14, pady=(0,12))
    
    def _buscar_produto_por_id(self, id_: int):
        p= ProdutoRepo.buscar_por_id(id_)
        if p:
            self._ean.set(p.ean)
            self._on_leitura_ean(p.ean)
    
    def _atualizar_total(self):
        try:
            qtd= int(self._quantidade.get() or "0")
            vunt= Decimal(self._valor_unit.get().replace(",",".") or "0")
            total= qtd*vunt
            self._lbl_total.configure(text=f"Valor total calculado: R$ {total:,.2f}")
        except Exception:
            self._lbl_total.configure(text="Valor total: -")
    
    def _parse_date(self, texto: str)-> date | None:
        #Aceita DD/MM?/AAAA ou AAAA-MM-DD
        texto= texto.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                continue
        return None
    
    def _salvar(self):
        if not self._produto_sel:
            self._banner.erro("Leia ou digite o código de barras para identificar o produto.")
            return
        
        #validar campos
        valido= all([
            self._num_lote.validar(),
            self._nota_fiscal.validar(),
            self._data_venc.validar(),
            self._quantidade.validar(),
            self._valor_unit.validar(),
        ])
        if not valido:
            return
        
        data_venc= self._parse_date(self._data_venc.get())
        if not data_venc:
            self._data_venc.erro("Data inválida. Use DD/MM/AAAA ou AAAA-MM-DD.")
            return
        data_fab= None
        if self._data_fab.get():
            data_fab= self._parse_date(self._data_fab.get())
            if not data_fab:
                self._data_fab.erro("Data inválida. Use DD/MM/AAAA ou AAAA-MM-DD.")
                return
        
        try:
            qtd= int(self._quantidade.get())
            if qtd <= 0:
                raise ValueError
        except ValueError:
            self._quantidade.erro("Informe um número inteiro positivo.")
            return
        
        try:
            vunt= Decimal(self._valor_unit.get().replace(",",".")) 
            if vunt <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            self._valor_unit.erro("Informe um valor unitário positivo.")
            return
        
        try:
            EstoqueService.registrar_entrada_manual(
                produto_id       =self._produto_sel.id,
                num_lote             =self._num_lote.get(), 
                nota_fiscal          =self._nota_fiscal.get(),
                data_vencimento      =data_venc,
                data_fabricacao      =data_fab,
                quantidade           =qtd,
                valor_unitario       =vunt,
                usuario_id           =self._usuario.id,
            )
            self._banner.sucesso(
                f"Entrada resgistrada: {qtd} unidade(s) de {self._produto_sel.nome}."
                f"lote: {self._num_lote.get()}"
            )
            self._limpar()

            #Disparar verificação de estoque miínimo
            self._verificar_estoque_pos_entrada()
        
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao registrar entrada: %s", exc)
            self._banner.erro(f"Erro ao registrar: {exc}")
        
    def _verificar_estoque_pos_entrada(self):
        #apos entrada, exibe aviso se estoque ainda está abaixo do minímo.
        if not self._produto_sel:
            return
        saldo= LoteRepo.saldo_total_produto(self._produto_sel.id)
        minimo= self._produto_sel.estoque_minimo
        if minimo>0 and saldo<= minimo:
            self._banner.erro(
                f"Atenção: saldo atual({saldo}) ainda está abaixo do estoque mínimo({minimo})",
                duração_ms=6000
            )
    
    def _limpar(self):
        self._produto_sel= None
        self._ean.limpar()
        self._card_produto.pack_forget()
        self._btn_cadastrar.pack_forget()
        for campo in [self._num_lote, self._nota_fiscal, self._data_fab,
                      self._data_venc, self._quantidade, self._valor_unit]:
            campo.limpar()
        self._lbl_total.configure(text="Valor total: -")
        self._ean.focus()
        