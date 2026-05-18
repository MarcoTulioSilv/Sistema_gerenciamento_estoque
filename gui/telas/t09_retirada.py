"""
gui.telas. t09_retirada.py
Tela t-09- Registro de retirada multi-lote FEFO
(UC-06, RF-07, RF-09, RN-08)
Dois modos de operação controlados por parâmetros do __init__:

  modo normal  (padrão)
      - produto_id: pré-seleciona um produto (atalho de T-10)
      - Dropdown "Centro de destino" aparece quando o produto possui apenas
        um centro de alocação e o usuário quer transferir para o outro.

  modo baixa_vencido  (baixa_vencido=True)
      - Campo EAN bloqueado, produto já fixado em produto_id.
      - Mostra APENAS lotes com data_vencimento < hoje (vencidos).
      - Título da topbar: "Baixa de produtos vencidos".
      - Tipo de movimentação gravado: TipoMovimentacaoEnum.baixa_vencido.
      - Dropdown de destino de centro ocultado (baixa não transfere).
      - Após confirmar: retorna para "inicio" em vez de "produtos".
"""

import logging 
from decimal import InvalidOperation

import customtkinter as ctk
from tkinter import messagebox
from gui.componentes.form_widgets import(   Campo, CampoBarras, CampoNome, SecaoFormulario, FeedbackBanner)
from Modulo_02_estoque import EstoqueService, LoteRepo, ProdutoRepo
from datetime import date
from Modulo_06_dados import CentroAlocacaoEnum, TipoMovimentacaoEnum
from Modulo_02_estoque import EstoqueService, LoteRepo, ProdutoRepo

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

_CENTROS= [c.value for c in CentroAlocacaoEnum]
_CENTROS_LABEL={
    "almoxarifado": "Almoxarifado",
    "farmacia": "Farmácia",
    "deposito": "Depósito",
}

class TelaRetirada(ctk.CTkFrame):
    #Registro de retirada com plano FEFO multi-lote exibido antes da confirmação.

    def __init__(self, master, usuario,on_navigate, produto_id: int=None, baixa_vencido: bool=False):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario= usuario
        self._on_navigate= on_navigate
        self._produto_sel= None
        self._plano= None
        self._baixa_vencido= baixa_vencido
        self._construir()   
        if produto_id:
            self._buscar_produto_por_id(produto_id)

    #_________ Construção______________________________________________________________
    def _construir(self):
        titulo = "Baixa de produtos vencidos" if self._baixa_vencido else "Registro de retirada"
        
        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44,corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text=titulo,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        # Badge de modo baixa
        if self._baixa_vencido:
            ctk.CTkLabel(
                topbar,
                text="  VENCIDOS — somente baixa  ",
                fg_color="#FCEBEB", text_color=COR_VERM,
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=6,
            ).pack(side="left", padx=(0, 12), pady=10)

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

        

        self._campo_nome= CampoNome(row_id, label="Nome do Produto",
            on_leitura= self._ao_ler_nome)
        self._campo_nome.grid(row=0,column=1, padx=(0,4), sticky="ew")
        
        #No modo baixa, EAN e nome bloqueados
        if self._baixa_vencido:
                    self._campo_ean._widget.configure(state="disabled")
                    self._campo_nome._widget.configure(state="disabled")
        self._campo_qtd= Campo(sec1, "Quantidade a retirar",
                               obrigatorio=True, tipo="number", placeholder="0")
        self._campo_qtd.pack(fill="x", padx=14, pady=(0,8))
        self._campo_qtd._widget.bind("<Return>", lambda e: self._calcular_plano())


        #Card produto encontrado
        self._frame_produto= ctk.CTkFrame(sec1, fg_color=COR_VERDE_BG,
                                          corner_radius=6, border_width=1, 
                                          border_color="#97C459")
        self._lbl_produto= ctk.CTkLabel(
            self._frame_produto,text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), justify="left", anchor="w")
        self._lbl_produto.pack(fill="x", padx=12, pady=8)

        # ── Centro de destino (só no modo normal) ────────────────────────────
        if not self._baixa_vencido:
            self._frame_destino = ctk.CTkFrame(sec1, fg_color="transparent")
            # Será exibido via _mostrar_destino() quando aplicável

            ctk.CTkLabel(
                self._frame_destino,
                text="Centro de destino (transferência):",
                font=ctk.CTkFont(size=12),
                text_color="#3d3d3a",
            ).pack(side="left", padx=(14, 8))

            self._opt_destino = ctk.CTkOptionMenu(
                self._frame_destino,
                values=["— sem transferência —"] + [_CENTROS_LABEL[c] for c in _CENTROS],
                width=200, height=32, corner_radius=6,
                fg_color=COR_BRANCO, button_color=COR_AZUL_M,
                text_color="#3d3d3a",
            )
            self._opt_destino.set("— sem transferência —")
            self._opt_destino.pack(side="left")

            ctk.CTkLabel(
                self._frame_destino,
                text="Movimenta as unidades para outro centro após a retirada.",
                text_color="#888780", font=ctk.CTkFont(size=10),
            ).pack(side="left", padx=10)
        else:
            self._frame_destino = None
            self._opt_destino   = None

        ctk.CTkButton(sec1, text="Calcular plano de retirada ->",
                      width=200, height=32,
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

        label_cancelar = "Voltar" if self._baixa_vencido else "Cancelar"
        destino_cancelar = "inicio" if self._baixa_vencido else "produtos"

        ctk.CTkButton(
            self._row_btns, text=label_cancelar,
            width=100, height=36,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B,
            hover_color=COR_CINZA_E,
            command=lambda: self._on_navigate(destino_cancelar),
        ).pack(side="left", padx=(0, 8))

        texto_confirmar = "Confirmar baixa" if self._baixa_vencido else "Confirmar retirada"
        cor_confirmar   = COR_VERM if self._baixa_vencido else "#1D9E75"
        hover_confirmar = "#7a1f1f" if self._baixa_vencido else "#0F6E56"

        self._btn_confirmar= ctk.CTkButton(
            self._row_btns, text=texto_confirmar,
            width=180, height=36, 
            fg_color=cor_confirmar, hover_color=hover_confirmar,
            state="disabled",
            command=self._confirmar)
        
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
        
        # No modo baixa: filtra só lotes vencidos
        if self._baixa_vencido:
            lotes = [
                l for l in LoteRepo.listar_por_produto(produto.id)
                if l.data_vencimento < date.today() and l.quantidade_atual > 0
            ]
            saldo = sum(l.quantidade_atual for l in lotes)
            descricao_saldo = f"Saldo vencido: {saldo} unid. em {len(lotes)} lote(s)"
        else:
            lotes = LoteRepo.listar_por_produto(produto.id)
            saldo = sum(
                l.quantidade_atual for l in lotes
                if l.data_vencimento >= date.today()
            )
            descricao_saldo = (
                f"Saldo disponível: {saldo} unid. em "
                f"{len([l for l in lotes if l.quantidade_atual > 0])} lote(s)"
            )
        
        self._campo_ean.erro("")
        self._produto_sel= produto
        self._lbl_produto.configure(
            text=(f"{produto.nome}\n"
                  f"Centro de alocação: {produto.centro_alocacao.value.capitalize()}.\n"
                    f"{descricao_saldo}")
                    )
        self._frame_produto.pack(fill="x", padx=14, pady=(0,8))

        # Atualiza opções de destino (só no modo normal)
        if not self._baixa_vencido and self._frame_destino is not None:
            self._atualizar_opcoes_destino(produto)
        
        self._plano= None
        self._sec2.pack_forget()
        self._btn_confirmar.configure(state="disabled")
        self._row_btns.pack_forget()
    
    def _ao_ler_nome(self, nome:str):
        try:
            produto= EstoqueService.buscar_produto_por_nome(nome)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto:{exc}")
            return
        
        if produto is None:
            self._campo_nome.erro(f"Nome '{nome}' não cadastrado.")
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

        # Atualiza opções de destino (só no modo normal)
        if not self._baixa_vencido and self._frame_destino is not None:
            self._atualizar_opcoes_destino(produto)
        
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
    
    def _atualizar_opcoes_destino(self, produto):
        """Popula o dropdown com os centros diferentes do centro atual do produto."""
        outros = [c for c in _CENTROS if c != produto.centro_alocacao.value]
        opcoes = ["— sem transferência —"] + [_CENTROS_LABEL[c] for c in outros]
        self._opt_destino.configure(values=opcoes)
        self._opt_destino.set("— sem transferência —")
        self._frame_destino.pack(fill="x", padx=14, pady=(0, 8))

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
            if self._baixa_vencido:
                plano = EstoqueService.calcular_plano_fefo(
                    self._produto_sel.id, qtd, apenas_vencidos=True
                )
            else:
                plano= EstoqueService.calcular_plano_fefo(self._produto_sel.id, qtd)
            
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
        destino_centro = None
        tipo_mov       = None

        if self._baixa_vencido:
            tipo_mov = TipoMovimentacaoEnum.baixa_vencido
        elif self._opt_destino is not None:
            sel = self._opt_destino.get()
            if sel != "— sem transferência —":
                # Reverter label → valor enum
                destino_centro = next(
                    (c for c in _CENTROS if _CENTROS_LABEL[c] == sel), None
                )
        try:
            estoque_baixo= EstoqueService.registrar_retirada(
                self._plano, self._usuario.id, obs, destino_centro=destino_centro,tipo_mov=tipo_mov)
            if self._baixa_vencido:
                msg = (
                    f"Baixa registrada: {self._plano.quantidade_pedida} unid. "
                    f"de '{self._produto_sel.nome}' removidas do estoque."
                )
            elif destino_centro:
                label_dest = _CENTROS_LABEL.get(destino_centro, destino_centro)
                msg = (
                    f"Transferência registrada: {self._plano.quantidade_pedida} unid. "
                    f"de '{self._produto_sel.nome}' → {label_dest}."
                )
            else:
                msg = (
                    f"Retirada registrada: {self._plano.quantidade_pedida} unid. "
                    f"de '{self._produto_sel.nome}'."
                )
            if estoque_baixo:
                msg += "\n Estoque abaixo do mínimo- alerta enviado."
            self._banner.sucesso(msg)
            # No modo baixa retorna para início; no normal, limpa para nova retirada
            if self._baixa_vencido:
                self.after(1500, lambda: self._on_navigate("inicio"))

            else:
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
        if self._frame_destino is not None:
            self._frame_destino.pack_forget()
        if self._opt_destino is not None:
            self._opt_destino.set("— sem transferência —")
        self._campo_ean.focus()
