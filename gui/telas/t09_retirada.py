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

from Modulo_02_estoque import EstoqueService, LoteRepo, ProdutoRepo, PlanoManual, ItemPlanoManual 
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
        self._lotes_ui_rows=[]
        
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
        self._banner.pack(fill="x", padx=16)
        
        #label scrollavel 
        self.scroll= ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        self.scroll.pack(fill="both",expand=True)

        #----Passo 1: escolha do centro de retirada (só no modo normal)--------------------------------------
        self._sec_centro= SecaoFormulario(self.scroll, titulo="Centro de retirada")
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
        self._sec_produto= SecaoFormulario(self.scroll, titulo="Identificar produto")

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
        self._sec_operacao= SecaoFormulario(self.scroll, titulo="Tipo de operação")
        grid_op= ctk.CTkFrame(self._sec_operacao, fg_color="transparent")
        grid_op.pack(fill="x", padx=14, pady=(4,8))
        
        self._campo_qtd = Campo(grid_op, label="Quantidade a baixar(Vencidos)", obrigatorio=True, tipo="number", placeholder="0")
        
        if not self._baixa_vencido:
            ctk.CTkLabel(grid_op, text="Transferir para outro centro?", 
                         font=ctk.CTkFont(size=12, weight="bold"), text_color="#3d3d3a").pack(side="left", padx=(0,12))
            self._toggle_transf_var = ctk.BooleanVar(value=False)
            self._toggle_transf = ctk.CTkSwitch(grid_op, text="", variable=self._toggle_transf_var,
                                                width=46, height=24,
                                                button_color=COR_VERDE_T, progress_color=COR_VERDE_T,
                                                command=self._ao_mudar_toggle_transf)
            self._toggle_transf.pack(side="left")
        else:
            self._campo_qtd.pack(side="left", padx=(0,24))
            ctk.CTkButton(grid_op, text="Calcular Baixa", width=140, height=32, 
                          fg_color=COR_AZUL_M, command= self._calcular_plano).pack(side="left", pady=14)
            
        # Subseção de transferência (oculta por padrão)
        self._sec_transf = ctk.CTkFrame(
            self._sec_operacao, fg_color="#E6F1FB",
            corner_radius=6, border_width=1, border_color=COR_AZUL_M)
        ctk.CTkLabel(self._sec_transf, text="Selecione o centro de destinino:", text_color=COR_AZUL,
                     font=ctk.CTkFont(size=11), justify="left", anchor="w").pack(fill="x", padx=12, pady=(8, 4))
   
        row_t = ctk.CTkFrame(self._sec_transf, fg_color="transparent")
        row_t.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(row_t, text="Centro de destino",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#3d3d3a").pack(side="left", padx=(0,8))
        
        self._opt_centro_dest = ctk.CTkOptionMenu(
            row_t, values=list(_CENTROS.values()),
            width=180, height=30, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a")
        self._opt_centro_dest.pack(side="left")


        #-----Passo 4: Listagem e seleção de Lotes-----------------------------------------------------------
        self._sec_plano = SecaoFormulario(self.scroll, titulo="4. Selecione os Lotes e Determine as quantidades")
 
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
        self._sec_obs = SecaoFormulario(self.scroll, titulo="Observações")
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
        self._row_btns = ctk.CTkFrame(self.scroll, fg_color="transparent")
 
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
            self._sec_operacao.pack_forget()
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
                         and  (l.data_vencimento is None or l.data_vencimento >= hoje)
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

        self._sec_operacao.pack(fill="x", padx=16, pady=(10, 0))
        if not self._baixa_vencido:
            self._listar_lotes_para_selecao_manual(lotes_vis)
        else: 
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
    # Passo 3 — Toggle de transferência e Seleção manual de lotes
    # ══════════════════════════════════════════════════════════════════════════

    def _ao_mudar_toggle_transf(self):
        if self._toggle_transf_var.get():
            self._sec_transf.pack(fill="x", padx=14, pady=(0, 10))
            self._btn_confirmar.configure(text="Confirmar transferência")
        else:
            self._sec_transf.pack_forget()
            self._btn_confirmar.configure(text="Confirmar retirada")
    

    def _listar_lotes_para_selecao_manual(self, lotes_disponiveis):
        """Renderiza tuplas com Checkbox e Campo de Qtd (desativado por padrão)."""
        for w in self._frame_plano.winfo_children():
            w.destroy()
        self._lotes_ui_rows.clear()
        
        if not lotes_disponiveis:
            ctk.CTkLabel(self._frame_plano, text="Nenhum lote com saldo disponível neste centro.", text_color="#888780", font=ctk.CTkFont(size=12)).pack(pady=16)
            self._btn_confirmar.configure(state="disabled")
            self._sec_plano.pack(fill="x", padx=16, pady=(10, 0))
            return

        ctk.CTkLabel(self._frame_plano, text="Marque os lotes que deseja retirar e informe a quantidade:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_AZUL, anchor="w").pack(fill="x", padx=10, pady=(8,6))
        
        for lote in lotes_disponiveis:
            linha = ctk.CTkFrame(self._frame_plano, fg_color=COR_BRANCO, corner_radius=6, border_width=1, border_color=COR_CINZA_B)
            linha.pack(fill="x", padx=10, pady=3)
            
            var_check = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(linha, text="", variable=var_check, width=24, fg_color=COR_AZUL_M, hover_color="#1a5276")
            chk.grid(row=0, column=0, padx=(10,0), pady=10, sticky="w")

            venc_str = lote.data_vencimento.strftime('%d/%m/%Y') if lote.data_vencimento else "Uso Contínuo"
            dados = [
                (f"Lote: {lote.num_lote or 'S/L'}", 160, COR_AZUL, True),
                (f"Validade: {venc_str}", 130, "#888780", False),
                (f"Saldo Atual: {lote.quantidade_atual}", 120, "#3d3d3a", True)
            ]
            for col, (txt, w, cor, bold) in enumerate(dados, start=1):
                ctk.CTkLabel(linha, text=txt, width=w, anchor="w", font=ctk.CTkFont(size=11, weight="bold" if bold else "normal"), text_color=cor).grid(row=0, column=col, padx=6, pady=10, sticky="w")

            ctk.CTkLabel(linha, text="Qtd:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#3d3d3a").grid(row=0, column=4, padx=(10,2), pady=10, sticky="e")
            entry_qtd = ctk.CTkEntry(linha, width=70, height=28, corner_radius=6, justify="center", state="disabled", fg_color="transparent")
            entry_qtd.grid(row=0, column=5, padx=(0,10), pady=8, sticky="w")

            # Handler do Checkbox para Ativar/Desativar o campo de digitação
            chk.configure(command=lambda c=var_check, e=entry_qtd: self._ao_alternar_check_lote(c, e))
            
            self._lotes_ui_rows.append({"lote": lote, "var_check": var_check, "entry_qtd": entry_qtd})

        self._sec_plano.pack(fill="x", padx=16, pady=(10, 0))
        self._sec_obs.pack(fill="x", padx=16, pady=(6, 0))
        self._btn_confirmar.configure(state="normal")
        self._row_btns.pack(anchor="e", padx=16, pady=(0, 16))
        self._resetar_scroll()

    def _ao_alternar_check_lote(self, var_check, entry_widget):
        """Habilita a inserção apenas se o checkbox estiver selecionado."""
        if var_check.get():
            entry_widget.configure(state="normal", fg_color=COR_BRANCO, border_color=COR_AZUL_M)
            entry_widget.focus()
        else:
            entry_widget.delete(0, "end")
            entry_widget.configure(state="disabled", fg_color="transparent", border_color=COR_CINZA_B)

   
    # ══════════════════════════════════════════════════════════════════════════
    # Passo 4 — Cálculo e exibição do plano FEFO
    # ══════════════════════════════════════════════════════════════════════════

    def _calcular_plano(self):
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

    def _exibir_plano_vencidos(self, plano):
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
            text=(f"Serão baixadas{plano.quantidade_pedida} unidade(s)"
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
                
            nun_lote_str= item.num_lote if item.num_lote else"S/L"
            venc_str = item.data_vencimento.strftime('%d/%m/%Y') if item.data_vencimento else "Uso Contínuo"
            nf_str= item.nota_fiscal if item.nota_fiscal else "S/N"

            dados = [
                (f" Lote {nun_lote_str}",                              180, COR_VERM,   True),
                (f"Vence: {venc_str}", 160, "#888780",  False),
                (f"NF: {nf_str}",                             120, "#888780",  False),
                (f"{item.unidade_estoque.capitalize()}",                 90, "#3d3d3a",  False),
                (f"Atual: {item.saldo_atual}",                          100, "#3d3d3a",  False),
                (f"Retirar: {item.qtd_a_retirar}",                      140, COR_VERM, True),
            ]
            for col, (txt, w, cor, bold) in enumerate(dados):
                ctk.CTkLabel(
                linha, text=txt, width=w, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold" if bold else "normal"),
                text_color=cor,
            ).grid(row=0, column=col, padx=8, pady=8, sticky="w")

 
        self._sec_plano.pack(fill="x", padx=16, pady=(10, 0))
        self._sec_obs.pack(fill="x", padx=16, pady=(6, 0))
        self._btn_confirmar.configure(state="normal")
        self._row_btns.pack(anchor="e", padx=16, pady=(0, 16))        

    # ══════════════════════════════════════════════════════════════════════════
    # Passo 5 — Confirmação
    # ══════════════════════════════════════════════════════════════════════════

    def _confirmar(self):
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
        
        #----- Cenário B E C SELEÇÃO MANUAL DE LOTES -----------------------------------------------------------
        itens_manuais=[]
        for item_ui in self._lotes_ui_rows:
            if item_ui["var_check"].get():
                lote= item_ui["lote"]
                try:
                    qtd_digitada= int(item_ui["entry_qtd"].get())
                    if qtd_digitada <=0:
                        raise ValueError()
                    if qtd_digitada > lote.quantidade_atual:
                        raise ValueError(f"Quantidade digitada ({qtd_digitada}) "
                                         f"maior que saldo atual ({lote.quantidade_atual}).")
                except ValueError as exc:
                    self._banner.erro(f"Erro no lote {lote.num_lote or 'S/L'}: {exc}")
                    return
                itens_manuais.append(ItemPlanoManual(lote.id, lote.num_lote, qtd_digitada, lote.quantidade_atual, lote.unidade_estoque.value))

        if not itens_manuais:
            self._banner.erro("Selecione ao menos um lote para continuar.")
            return
        
        self._plano= PlanoManual(self._produto_sel.id, itens_manuais)
        
        if eh_transf:
            centro_dest_lb = self._opt_centro_dest.get()
            if centro_dest_lb == "— sem transferência —":
                self._banner.erro("Selecione o centro de destino.")
                return
            destino_centro = _LABEL_CENTRO.get(centro_dest_lb, centro_dest_lb.lower())
            
            try:
                EstoqueService.registrar_transferencia(
                    self._plano, self._usuario.id,
                    destino_centro      = destino_centro,
                    observacao          = obs,
                )
                unid_o = self._plano.unidade_estoque.capitalize()
                msg = (f"Transferência: {self._plano.quantidade_pedida} {unid_o} "
                           f"->'{centro_dest_lb}'.")
                self._banner.sucesso(msg)
                self._limpar()
            except ValueError as exc:
                self._banner.erro(str(exc),15000)
                logger.error("Erro na transferência: %s", exc)
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
            
            except Exception as exc:
                logger.error("Erro na retirada: %s", exc)
                self._banner.erro(f"Erro ao registrar: {exc}",15000)

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
        self._sec_operacao.pack_forget()
        self._limpar_plano()
        self._resetar_scroll()
 
    def _limpar_plano(self):
        """Oculta plano, observações e botões."""
        self._sec_plano.pack_forget()
        self._sec_obs.pack_forget()
        self._row_btns.pack_forget()
        self._btn_confirmar.configure(state="disabled")
        if not self._baixa_vencido:
            self._toggle_transf_var.set(False)
            self._sec_transf.pack_forget()
 
    def _limpar(self):
        """Reset completo para nova operação."""
        self._limpar_produto()
        self._campo_obs.delete(0, "end")
        if not self._baixa_vencido and not self._centro_origem:
            # Volta ao passo 1 se não há pré-seleção
            self._sec_produto.pack_forget()
            self._opt_centro.set(list(_CENTROS.values())[0])
            self._centro_origem = None
            
    def limpar_memoria(self):
        # Quebra o vínculo com objetos instanciados do banco de dados
        if hasattr(self, '_produto_sel'):
            self._produto_sel = None
        
        if hasattr(self, '_plano') and self._plano is not None:
            # O _plano tem uma lista de itens dentro dele que precisa ser solta
            self._plano = None
            
        if hasattr(self, '_lotes_vencidos'):
            self._lotes_vencidos = None

    def _resetar_scroll(self):
        """Força o redesenho da tela e joga o scroll para o topo."""
        # 1. Força a interface a recalcular o tamanho e layout dos widgets após pack_forget()
        self.update_idletasks()
        
        # 2. Acessa o Canvas interno do CustomTkinter e joga o scroll para o topo (posição 0.0)
        if hasattr(self, "_scroll") and hasattr(self._scroll, "_parent_canvas"):
            self._scroll._parent_canvas.yview_moveto(0.0)