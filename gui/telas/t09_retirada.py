"""
gui.telas. t09_retirada.py
Tela t-09- Registro de retirada multi-lote FEFO
(UC-06, RF-07, RF-09, RN-08)
Dois modos de operação controlados por parâmetros do __init__:

  modo normal  (padrão)
        Passo 1 → Escolha do centro de retirada
        Passo 2 → Identificação do produto (EAN ou nome)
        Passo 3 → Quantidade + toggle de transferência (renderiza subseção)
        Passo 4 → Plano FEFO calculado e exibido
        Passo 5 → Confirmação

  modo baixa_vencido  (baixa_vencido=True)
      - Campo EAN bloqueado, produto já fixado em produto_id.
      - Mostra APENAS lotes com data_vencimento < hoje (vencidos).
      - Título da topbar: "Baixa de produtos vencidos".
      - Tipo de movimentação gravado: TipoMovimentacaoEnum.baixa_vencido.
      - Dropdown de destino de centro ocultado (baixa não transfere).
      - Após confirmar: retorna para "inicio" em vez de "produtos".
  produto_id=N        — atalho de T-10; pula a etapa de busca.
  centro_origem=str   — pré-seleciona o centro (atalho de T-10).
"""

import logging 
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from gui.componentes.form_widgets import(   Campo, CampoBarras, CampoNome, SecaoFormulario, FeedbackBanner)

from Modulo_02_estoque import EstoqueService, LoteRepo, ProdutoRepo
from Modulo_06_dados import CentroAlocacaoEnum, TipoMovimentacaoEnum, UnidadeEstoqueEnum

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



_CENTROS: dict[str, str] = {
    c.value: c.value.capitalize() for c in CentroAlocacaoEnum
}
_LABEL_CENTRO: dict[str, str] = {v: k for k, v in _CENTROS.items()}

_UNIDADES: dict[str, str] = {
    u.value: u.value.capitalize() for u in UnidadeEstoqueEnum
}
_LABEL_UNIDADE: dict[str, str] = {v: k for k, v in _UNIDADES.items()}

class TelaRetirada(ctk.CTkFrame):
    #Registro de retirada com plano FEFO multi-lote exibido antes da confirmação.

    def __init__(
            self,
            master, 
            usuario, 
            on_navigate, 
            baixa_vencido: bool=False, 
            lotes_vencidos: list|None=None, 
            produto_id:int| None=None, 
            centro_origem:str| None=None
        ):

        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._baixa_vencido = baixa_vencido
        self._produto_sel = None
        self._plano = None
        self._centro_origem = centro_origem # pré-selecionado (t-10)
        
        # Configuração do laço sequencial de itens vencidos
        self._lotes_vencidos = lotes_vencidos or []
        self._vencido_index = 0
        
        self._construir()
        
        #Atalhos de entrada
        if produto_id:
            self._preencher_produto_por_id(produto_id)
        if self._baixa_vencido and self._lotes_vencidos:
            self._carregar_lote_vencido_atual()

    #_________ Construção__________________________________________________________________________

    def _construir(self):
        titulo = "Baixa de produtos vencidos" if self._baixa_vencido else "Registro de retirada"
        
        #--------------------Topbar----------------------------------------------------------------
        topbar= ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44,corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text=titulo,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        
        if self._baixa_vencido:
            ctk.CTkLabel(
                topbar,
                text="  VENCIDOS — somente baixa  ",
                fg_color="#FCEBEB", text_color=COR_VERM,
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=6).pack(side="left", padx=(0, 12), pady=10)

        self._banner= FeedbackBanner(self)
        
        #label scrollavel 
        scroll= ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both",expand=True)

        #----Passo 1: escolha do centro de retirada (só no modo normal)--------------------------------------
        self._sec_centro= SecaoFormulario(scroll, titulo="Centro de retirada")
        self._sec_centro.pack(fill="x", padx=16, pady=(12,0))

        row_c= ctk.CTkFrame(self._sec_centro, fg_color="transparent")
        row_c.pack(fill="x", padx=14, pady=(4,12))

        ctk.CTkLabel(row_c, text="Selecione o centro de retirada do produto:",
                     font=ctk.CTkFont(size=12), text_color="#3d3d3a").pack(side="left", padx=(0,12))
        
        self._opt_centro= ctk.CTkOptionMenu(
            row_c,
            values= list(_CENTROS.values()),
            width=160, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a",
            command=self._ao_escolher_centro,
        )
        self._opt_centro.pack(side="left")

        # Pré-selecionar centro se veio de atalho
        if self._centro_origem and self._centro_origem in _CENTROS:
            self._opt_centro.set(_CENTROS[self._centro_origem])
        elif self._baixa_vencido:
            # No modo baixa o centro não é relevante (frame ocultado)
            self._sec_centro.pack_forget()

        #-----Passo 2: identificação do produto (oculto até escolha do centro)--------------------------------------
        self._sec_produto= SecaoFormulario(scroll, titulo="Identificar produto")

        row_id= ctk.CTkFrame(self._sec_produto, fg_color="transparent")
        row_id.pack(fill="x", padx=14, pady=(4,8))
        row_id.grid_columnconfigure((0, 1), weight=1)

        self._campo_ean = CampoBarras(
            row_id, label="Código de barras (EAN)",
            on_leitura=self._ao_ler_ean)
        self._campo_ean.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        self._campo_nome = CampoNome(
            row_id, label="Nome do produto",
            on_leitura=self._ao_ler_nome)
        self._campo_nome.grid(row=0, column=1, padx=(0, 4), sticky="ew")

        if self._baixa_vencido:
            self._campo_ean._entry.configure(state="disabled")
            self._campo_nome._entry.configure(state="disabled")

        # Card de produto encontrado
        self._frame_produto = ctk.CTkFrame(
            self._sec_produto, fg_color=COR_VERDE_BG,
            corner_radius=6, border_width=1, border_color="#97C459")
        self._lbl_produto = ctk.CTkLabel(
            self._frame_produto, text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), justify="left", anchor="w")
        self._lbl_produto.pack(fill="x", padx=12, pady=8)

        #------Passo 3: Quantidade+ toggle de transferência-------------------------------------------
        self._sec_qtd = SecaoFormulario(scroll, titulo="3. Quantidade e destino")
 
        grid_q = ctk.CTkFrame(self._sec_qtd, fg_color="transparent")
        grid_q.pack(fill="x", padx=14, pady=(4, 8))
        grid_q.grid_columnconfigure((0, 1, 2), weight=1)
 
        self._campo_qtd = Campo(
            grid_q, "Quantidade a retirar",
            obrigatorio=True, tipo="number", placeholder="0")
        self._campo_qtd.grid(row=0, column=0, sticky="w", padx=(0, 24))
        
        # Toggle de transferência (oculto no modo baixa)
        if not self._baixa_vencido:
            ctk.CTkLabel(grid_q, text="Transferir para outro centro?",
                         font=ctk.CTkFont(size=11), text_color="#3d3d3a").grid(
                row=0, column=1, sticky="w")
 
            self._toggle_transf_var = ctk.BooleanVar(value=False)
            self._toggle_transf = ctk.CTkSwitch(
                grid_q, text="", variable=self._toggle_transf_var,
                width=46, height=24,
                button_color=COR_VERDE_T, progress_color=COR_VERDE_T,
                command=self._ao_mudar_toggle_transf)
            self._toggle_transf.grid(row=0, column=2, sticky="w")

        # Subseção de transferência (oculta por padrão)
        self._sec_transf = ctk.CTkFrame(
            self._sec_qtd, fg_color="#E6F1FB",
            corner_radius=6, border_width=1, border_color=COR_AZUL_M)
        
        ctk.CTkLabel(
            self._sec_transf,
            text="O SCE define o lote de origem. O restante do lote fica no centro original.",
            text_color=COR_AZUL, font=ctk.CTkFont(size=11),
            justify="left", anchor="w", wraplength=620,
        ).pack(fill="x", padx=12, pady=(8, 4))
        
        row_t = ctk.CTkFrame(self._sec_transf, fg_color="transparent")
        row_t.pack(fill="x", padx=12, pady=(0, 10))
        row_t.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(row_t, text="Centro de destino",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#3d3d3a").grid(row=0, column=0, sticky="w")
        self._opt_centro_dest = ctk.CTkOptionMenu(
            row_t, values=list(_CENTROS.values()),
            width=160, height=30, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a",
            command=self._ao_mudar_centro_dest)
        self._opt_centro_dest.grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(2, 0))

        ctk.CTkLabel(row_t, text="Fator (unid. por embalagem)",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#3d3d3a").grid(row=0, column=1, sticky="w")
        frame_fator = ctk.CTkFrame(row_t, fg_color="transparent")
        frame_fator.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(2, 0))
        self._entry_fator = ctk.CTkEntry(frame_fator, width=70, height=30, corner_radius=6)
        self._entry_fator.insert(0, "1")
        self._entry_fator.pack(side="left")
        self._entry_fator.bind("<FocusOut>", lambda e: self._ao_mudar_fator())
        self._entry_fator.bind("<Return>", lambda e: self._ao_mudar_fator())

        ctk.CTkLabel(row_t, text="Unidade de destino",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#3d3d3a").grid(row=0, column=2, sticky="w")
        self._opt_unidade_dest = ctk.CTkOptionMenu(
            row_t, values=list(_UNIDADES.values()),
            width=150, height=30, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a")
        self._opt_unidade_dest.grid(row=1, column=2, sticky="w", pady=(2, 0))
        self._opt_unidade_dest.configure(state="disabled")

        self._lbl_preview = ctk.CTkLabel(
            self._sec_transf, text="", text_color=COR_AZUL_M,
            font=ctk.CTkFont(size=11), anchor="w")
        self._lbl_preview.pack(fill="x", padx=12, pady=(0, 6))

        # Botão calcular plano
        ctk.CTkButton(
            self._sec_qtd, text="Calcular plano de retirada →",
            width=210, height=32,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=12),
            command=self._calcular_plano,
        ).pack(anchor="w", padx=14, pady=(8, 12))

        #-----Passp 4: Plano de consumo-----------------------------------------------------------
        self._sec_plano = SecaoFormulario(scroll, titulo="4. Plano de consumo")
 
        self._frame_plano = ctk.CTkFrame(
            self._sec_plano, fg_color=COR_CINZA_E, corner_radius=6)
        self._frame_plano.pack(fill="x", padx=14, pady=(0, 8))
 
        self._frame_insuf = ctk.CTkFrame(
            self._sec_plano, fg_color="#FCEBEB",
            corner_radius=6, border_width=1, border_color="#F09595")
        self._lbl_insuf = ctk.CTkLabel(
            self._frame_insuf, text="", text_color=COR_VERM,
            font=ctk.CTkFont(size=12), justify="left")
        self._lbl_insuf.pack(fill="x", padx=12, pady=8)

        #----- Observações---------------------------------------------------------------------------
        self._sec_obs = SecaoFormulario(scroll, titulo="Observações")
        self._campo_obs = ctk.CTkEntry(
            self._sec_obs,
            placeholder_text="Ex: Retirada para enfermaria 2 — Dr. Silva",
            height=34, corner_radius=6)
        self._campo_obs.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkLabel(self._sec_obs,
                     text="Quando preenchido, aparece em todos os registros desta retirada.",
                     text_color="#888780", font=ctk.CTkFont(size=10)).pack(
            anchor="w", pady=(0, 12))
        
        #----- Botões---------------------------------------------------------------------------
        self._row_btns = ctk.CTkFrame(scroll, fg_color="transparent")
 
        label_cancelar   = "Voltar"   if self._baixa_vencido else "Cancelar"
        destino_cancelar = "inicio"   if self._baixa_vencido else "produtos"
        texto_confirmar  = "Confirmar baixa" if self._baixa_vencido else "Confirmar retirada"
        cor_confirmar    = COR_VERM if self._baixa_vencido else "#1D9E75"
        hover_confirmar  = "#7a1f1f" if self._baixa_vencido else "#0F6E56"
 
        ctk.CTkButton(
            self._row_btns, text=label_cancelar,
            width=100, height=36,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
            command=lambda: self._on_navigate(destino_cancelar),
        ).pack(side="left", padx=(0, 8))
 
        self._btn_confirmar = ctk.CTkButton(
            self._row_btns, text=texto_confirmar,
            width=190, height=36,
            fg_color=cor_confirmar, hover_color=hover_confirmar,
            state="disabled",
            command=self._confirmar)
        self._btn_confirmar.pack(side="left")

        # Estado inicial: passo 2 em diante oculto
        # No modo baixa ou pré-seleção ja mostra o passo 2
        if self._baixa_vencido or self._centro_origem:
            self._mostrar_sec_produto()
        else:
            self._sec_produto.pack_forget()
            self._sec_qtd.pack_forget()
            self._sec_plano.pack_forget()
            self._sec_obs.pack_forget()
            self._row_btns.pack_forget()

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 1 — Escolha do centro
    # ══════════════════════════════════════════════════════════════════════════

    def _ao_escolher_centro(self, label:str):
        # Callback do OptionMenu de centro- revela passo 2
        self._centro_origem = _LABEL_CENTRO.get(label, label.lower())
        self._mostrar_sec_produto()
        # Atualizar opções de destino excluindo o centro de origem
        outros = ["— sem transferência —"] + [
            lb for val, lb in _CENTROS.items() if val != self._centro_origem
        ]
        self._opt_centro_dest.configure(values=outros)
        self._opt_centro_dest.set("— sem transferência —")
        # Limpar produto selecionado caso tenha trocado de centro
        self._limpar_produto()
    
    def _mostrar_sec_produto(self):
        self._sec_produto.pack(fill="x", padx=16, pady=(10,0))
        self._campo_ean.focus()

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 2 — Identificação do produto
    # ══════════════════════════════════════════════════════════════════════════

    def _ao_ler_ean(self, ean:str):
        self._buscar_e_exibir(EstoqueService.buscar_produto_por_ean, ean, 
                              erro_msg=f"EAN '{ean}' não cadastrado.")
    

    
    def _ao_ler_nome(self, nome:str):
        self._buscar_e_exibir(EstoqueService.buscar_produto_por_nome, nome,
                                erro_msg=f"Produto '{nome}' não encontrado.")
    
    def _buscar_e_exibir(self, func_busca, valor: str, erro_msg: str):
        if not self._centro_origem and not self._baixa_vencido:
            self._banner.erro("Selecione o centro de retirada antes de buscar o produto.")
            return
        try:
            produto = func_busca(valor)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return
 
        if produto is None:
            self._banner.erro(erro_msg)
            self._frame_produto.pack_forget()
            self._produto_sel = None
            return
        
        hoje = date.today()
        lotes = LoteRepo.listar_por_produto(produto.id)
 
        if self._baixa_vencido:
            lotes_vis = [l for l in lotes
                         if l.quantidade_atual > 0 and l.data_vencimento < hoje]
        else:
            lotes_vis = [l for l in lotes
                         if l.quantidade_atual > 0
                         and l.data_vencimento >= hoje
                         and l.centro_alocacao.value == self._centro_origem]
 
        saldo   = sum(l.quantidade_atual for l in lotes_vis)
        n_lotes = len(lotes_vis)

        # Unidades distintas presentes no centro
        unidades = list({l.unidade_estoque.value for l in lotes_vis})
        unid_txt = " / ".join(u.capitalize() for u in unidades) or "—"
 
        self._produto_sel = produto
        self._lbl_produto.configure(
            text=(
                f"{produto.nome}\n"
                f"Saldo em '{(_CENTROS.get(self._centro_origem or '', '—'))}': "
                f"{saldo} unid. em {n_lotes} lote(s)  ·  Unidade: {unid_txt}"
            )
        )
        self._frame_produto.pack(fill="x", padx=14, pady=(0, 8))

        # Revela o passo 3
        self._sec_qtd.pack(fill="x", padx=16, pady=(10, 0))
        self._limpar_plano()
    
    def _preencher_produto_por_id(self, produto_id: int):
        try:
            p = ProdutoRepo.buscar_por_id(produto_id)
            if p:
                self._campo_ean.set(p.ean)
                self._campo_nome.set(p.nome)
                self._ao_ler_ean(str(p.ean))
        except Exception as exc:
            logger.error("Erro ao pré-selecionar produto: %s", exc)
    
    # ══════════════════════════════════════════════════════════════════════════
    # Passo 3 — Toggle de transferência
    # ══════════════════════════════════════════════════════════════════════════

    def _ao_mudar_toggle_transf(self):
        if self._toggle_transf_var.get():
            self._sec_transf.pack(fill="x", padx=14, pady=(0, 10))
            self._btn_confirmar.configure(text="Confirmar transferência")
        else:
            self._sec_transf.pack_forget()
            self._entry_fator.delete(0, "end")
            self._entry_fator.insert(0, "1")
            self._lbl_preview.configure(text="")
    
    def _ao_mudar_centro_dest(self, _valor: str):
        self._ao_mudar_fator()

    def _ao_mudar_fator(self):
        try:
            fator = int(self._entry_fator.get())
        except ValueError:
            fator = 1
 
        if fator > 1:
            self._opt_unidade_dest.configure(state="normal")
            qtd    = self._plano.quantidade_pedida if self._plano else 0
            unid_o = self._plano.unidade_estoque.capitalize() if self._plano else "unid."
            unid_d = _LABEL_UNIDADE.get(self._opt_unidade_dest.get(),
                                         self._opt_unidade_dest.get().lower())
            self._lbl_preview.configure(
                text=f"→ {qtd} {unid_o} × {fator} = {qtd * fator} {unid_d} no destino."
            )
        else:
            self._opt_unidade_dest.configure(state="disabled")
            self._lbl_preview.configure(text="")

   

    

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 4 — Cálculo e exibição do plano FEFO
    # ══════════════════════════════════════════════════════════════════════════

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
            plano= EstoqueService.calcular_plano_fefo(
                self._produto_sel.id,
                qtd,
                apenas_vencidos= self._baixa_vencido,
                centro_origem= self._centro_origem if not self._baixa_vencido else None,
            )
            
        except Exception as exc:
            self._banner.erro(f"Erro ao calcular plano: {exc}")
            logger.error("erro ao calcular plano: %s",exc)
            return
            

        self._plano= plano
        self._exibir_plano(plano)

    def _exibir_plano(self, plano):
        for w in self._frame_plano.winfo_children():
            w.destroy()

        if not plano.atendido_completo: 
                self._lbl_insuf.configure(
                    text=(
                    f"Estoque insuficiente para {plano.quantidade_pedida} unidade(s).\n"
                    f"Máximo disponível em '{_CENTROS.get(self._centro_origem or '', '?')}': "
                    f"{plano.quantidade_maxima_disponivel} unid.")
                )
                self._frame_insuf.pack(fill="x", padx=14, pady=(0,8))
                self._btn_confirmar.configure(state="disabled")
                self._sec_plano.pack(fill="x", padx=16, pady=(10,0))
                self._row_btns.pack(anchor="e", padx=16, pady=(0,16))
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

            dados = [
                (f" Lote {item.num_lote}",                              160, COR_AZUL,   True),
                (f"Vence: {item.data_vencimento.strftime('%d/%m/%Y')}", 150, "#888780",  False),
                (f"NF: {item.nota_fiscal}",                             120, "#888780",  False),
                (f"{item.unidade_estoque.capitalize()}",                 90, "#3d3d3a",  False),
                (f"Atual: {item.saldo_atual}",                          100, "#3d3d3a",  False),
                (f"Retirar: {item.qtd_a_retirar}",                      110, COR_AZUL_M, True),
            ]
            for col, (txt, w, cor, bold) in enumerate(dados):
                ctk.CTkLabel(
                linha, text=txt, width=w, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold" if bold else "normal"),
                text_color=cor,
            ).grid(row=0, column=col, padx=6, pady=7, sticky="w")

            cor_saldo= COR_VERM if item.lote_esgotado else COR_VERDE_T
            saldo_txt="0 - lote esgotado" if item.lote_esgotado else str(item.saldo_restante)   
            ctk.CTkLabel(
                linha, text=f"Restante: {saldo_txt}", width=170,
                font=ctk.CTkFont(size=11), text_color=cor_saldo, anchor="w",
            ).grid(row=0, column=6, padx=6, pady=7, sticky="w")    

        ctk.CTkLabel(
            self._frame_plano,
            text="Confirme abaixo para registrar.",
            text_color="#5F5E5A", font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=10, pady=(4, 8))
 
        self._sec_plano.pack(fill="x", padx=16, pady=(10, 0))
        self._sec_obs.pack(fill="x", padx=16, pady=(6, 0))
        self._btn_confirmar.configure(state="normal")
        self._row_btns.pack(anchor="e", padx=16, pady=(0, 16))        

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 5 — Confirmação
    # ══════════════════════════════════════════════════════════════════════════

    def _confirmar(self):
        if not self._plano:
            return
 
        obs          = self._campo_obs.get().strip() or None
        eh_transf    = (not self._baixa_vencido
                        and hasattr(self, "_toggle_transf_var")
                        and self._toggle_transf_var.get())
        #----- Cenário A: baixa de vencidos-----------------------------------------------------------
        if self._baixa_vencido:
            try:
                EstoqueService.registrar_retirada(
                    self._plano, self._usuario.id, obs, baixa_vencido=True)
                msg = (f"Baixa registrada: {self._plano.quantidade_pedida} unid. "
                       f"de '{self._produto_sel.nome}'.")
                self._banner.sucesso(msg)

                # Fila sequencial de vencidos
                if self._lotes_vencidos:
                    self._vencido_index += 1
                    if self._vencido_index < len(self._lotes_vencidos):
                        self._limpar()
                        self._carregar_lote_vencido_atual()
                    else:
                        messagebox.showinfo(
                            "Concluído",
                            "Todos os lotes vencidos listados foram baixados.")
                        self._on_navigate("inicio")
                else:
                    self._limpar()
            except ValueError as exc:
                self._banner.erro(str(exc))
            except Exception as exc:
                logger.error("Erro na baixa: %s", exc)
                self._banner.erro(f"Erro ao registrar: {exc}")
        
        #----- Cenário B: Transferência entre centros-----------------------------------------------------------
        elif eh_transf:
            centro_dest_lb = self._opt_centro_dest.get()
            if centro_dest_lb == "— sem transferência —":
                self._banner.erro("Selecione o centro de destino.")
                return
            destino_centro = _LABEL_CENTRO.get(centro_dest_lb, centro_dest_lb.lower())

            try:
                fator = int(self._entry_fator.get())
                if fator < 1:
                    raise ValueError()
            except ValueError:
                self._banner.erro("Fator de fracionamento inválido. Mínimo: 1.")
                return
            
            unidade_dest = None
            if fator > 1:
                unid_lb = self._opt_unidade_dest.get()
                unidade_dest = _LABEL_UNIDADE.get(unid_lb, unid_lb.lower())
                if not unidade_dest:
                    self._banner.erro("Selecione a unidade de destino.")
                    return
            
            try:
                EstoqueService.registrar_transferencia(
                    self._plano, self._usuario.id,
                    destino_centro      = destino_centro,
                    fator_fracionamento = fator,
                    unidade_destino     = unidade_dest,
                    observacao          = obs,
                )
                unid_o = self._plano.unidade_estoque.capitalize()
                if fator > 1:
                    qtd_dest = self._plano.quantidade_pedida * fator
                    msg = (f"Transferência: {self._plano.quantidade_pedida} {unid_o} → "
                           f"{qtd_dest} {unidade_dest} em '{centro_dest_lb}'.")
                else:
                    msg = (f"Transferência: {self._plano.quantidade_pedida} {unid_o} "
                           f"→ '{centro_dest_lb}'.")
                self._banner.sucesso(msg)
                self._limpar()
            except ValueError as exc:
                self._banner.erro(str(exc))
            except Exception as exc:
                logger.error("Erro na transferência: %s", exc)
                self._banner.erro(f"Erro ao registrar: {exc}")
        #----- Cenário C: Retirada simples-----------------------------------------------------------
        else: 
            try:
                estoque_baixo= EstoqueService.registrar_retirada(
                    self._plano, self._usuario.id, obs)
                msg=(f"Retirada registrada: {self._plano.quantidade_pedida} unid."
                     f"de '{self._produto_sel.nome}'.")
                if estoque_baixo:
                    msg+= "\n⚠ Estoque abaixo do mínimo — alerta enviado."
                self._banner.sucesso(msg)
                self._limpar()     
            
            except ValueError as exc:
                self._banner.erro(str(exc))
            except Exception as exc:
                logger.error("Erro na retirada: %s", exc)
                self._banner.erro(f"Erro ao registrar: {exc}")

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════════
    def _carregar_lote_vencido_atual(self):
        """Carrega o próximo lote da fila de baixa de vencidos."""
        if self._vencido_index >= len(self._lotes_vencidos):
            return
            
        item = self._lotes_vencidos[self._vencido_index]

        self._campo_ean._entry.configure(state="normal")
        self._campo_ean.set(item["ean"])
        self._campo_ean._entry.configure(state="disabled")
        self._ao_ler_ean(item["ean"])

        self._campo_qtd.set(str(item["quantidade"]))
        self._campo_obs.delete(0, "end")
        self._campo_obs.insert(0, f"Descarte lote vencido — Lote {item['lote']}")
        self._calcular_plano()  

        n_total = len(self._lotes_vencidos)
        self._btn_confirmar.configure(
            text="Confirmar e Próximo" if self._vencido_index < n_total - 1
            else "Confirmar e Finalizar")
        self._banner.aviso(
            f"Lote {item['lote']}  ({self._vencido_index + 1} de {n_total})")
                

    def _limpar_produto(self):
        """Limpa apenas a seleção de produto (mantém centro escolhido)."""
        self._produto_sel = None
        self._plano       = None
        self._campo_ean.limpar()
        self._campo_nome.limpar()
        self._frame_produto.pack_forget()
        self._sec_qtd.pack_forget()
        self._limpar_plano()
 
    def _limpar_plano(self):
        """Oculta plano, observações e botões."""
        self._sec_plano.pack_forget()
        self._sec_obs.pack_forget()
        self._row_btns.pack_forget()
        self._btn_confirmar.configure(state="disabled")
        if not self._baixa_vencido:
            self._toggle_transf_var.set(False)
            self._sec_transf.pack_forget()
            self._lbl_preview.configure(text="")
 
    def _limpar(self):
        """Reset completo para nova operação."""
        self._limpar_produto()
        self._campo_obs.delete(0, "end")
        if not self._baixa_vencido and not self._centro_origem:
            # Volta ao passo 1 se não há pré-seleção
            self._sec_produto.pack_forget()
            self._opt_centro.set(list(_CENTROS.values())[0])
            self._centro_origem = None