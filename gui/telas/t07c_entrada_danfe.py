"""
gui.telas.t07c_entrada_danfe.py
Tela T-07c — Entrada assistida por chave de acesso DANFE (RF-04b / ERS v1.6)

Fluxo com scraping automático (AD-12 revisado):
  1. Técnico lê 44 dígitos da chave com o leitor USB.
  2. DanfeEntryAssistant valida e extrai número da NF.
  3. SCE abre o portal SEFAZ via Selenium em thread separada.
  4. Técnico resolve o CAPTCHA no browser.
  5. Selenium detecta o resultado automaticamente e extrai os dados.
  6. SCE preenche os campos do lote com os dados extraídos.
  7. Fallback: se Selenium falhar → campos desbloqueados para preenchimento manual.
"""
import logging
import threading
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from gui.componentes.form_widgets import (
    CampoBarras, CampoNome, SecaoFormulario, FeedbackBanner, Campo
)
from Modulo_02_estoque import EstoqueService, ProdutoRepo, LoteRepo, DanfeEntryAssistant
from Modulo_02_estoque.sefaz_receiver import DadosSefaz  
logger = logging.getLogger(__name__)

COR_AZUL     = "#1F4E79"
COR_AZUL_M   = "#2E75B6"
COR_AZUL_L   = "#D6E4F0"
COR_CINZA_E  = "#F2F1ED"
COR_CINZA_B  = "#E8E6DE"
COR_BRANCO   = "#FFFFFF"
COR_VERDE_BG = "#EAF3DE"
COR_VERDE_T  = "#27500A"
COR_AMBER_BG = "#FAEEDA"
COR_AMBER_T  = "#854F0B"
COR_VERM     = "#A32D2D"
COR_VERM_BG  = "#FCEBEB"

UNIDADES = ["caixa", "pacote", "unidade", "ampola", "galao",
            "fardo", "litro", "rolo", "kit", "dose"]
CENTROS  = ["deposito", "almoxarifado", "farmacia"]

_unidade_MAP = {
    "CX":  "caixa",  "CXA": "caixa","C":"caixa","CAIXA":"caixa",

    "PCT": "pacote", "PC":  "pacote", "PACOTE": "pacote", "PT": "pacote",

    "UN":  "unidade", "UND": "unidade" ,"UNID": "unidade","UNIDADE": "unidade", "CDA":"unidade", "CD":"unidade", "CADA": "unidade",

    "AMP": "ampola","APL":"ampola", "AMPOLA":"ampola", "APL": "ampola", "AM": "ampola", "AP": "ampola",

    "GL":"galao", "GALÃO":"galao","GALAO":"galao", "GLA":"galao",

    "FRD":"fardo", "FAR":"fardo", "FARDO":"fardo", "FD": "fardo",

    "LTR": "litro", "LIT":"litro","LITRO":"litro", "LT": "litro",

    "RL":"rolo", "RO":"rolo","ROLO":"rolo", "RLO": "rolo",

    "KIT":"kit", "KT":"kit",

    "DOSE":"dose", "DS":"dose", "DO":"dose", "DSE": "dose"
}  

def _mapear_unidade(unidade_nfe:str)-> str:
    if not unidade_nfe:
        return "caixa"
    sigla = str(unidade_nfe).upper().strip()
    return _unidade_MAP.get(sigla, "caixa")


class TelaEntradaDANFE(ctk.CTkFrame):

    def __init__(self, master, usuario, on_navigate, produto_id: int = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario      = usuario
        self._on_navigate  = on_navigate
        self._produto_sel  = None
        self._dados_chave  = None      # dict de DanfeEntryAssistant.processar_chave()
        self._scraper      = None      # instância ativa de SefazScraperf
        self._ean_pendente = None
        self._construir()
        if produto_id:
            self._buscar_produto_por_id(produto_id)

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar,
                     text="Entrada via DANFE — Chave de Acesso",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
        ctk.CTkLabel(self._topbar,
                     text="Início › Estoque › Entrada DANFE",
                     font=ctk.CTkFont(size=11),
                     text_color="#888780").pack(side="left", padx=4)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)
       

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=COR_CINZA_E, corner_radius=8,
            border_width=1, border_color=COR_CINZA_B
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=8)

        self._construir_sec_chave()
        self._construir_sec_scraping()
        self._construir_sec_produto()
        self._construir_sec_lote()
        self._construir_botoes()

        # Seções ocultadas inicialmente
        self._sec_scraping.pack_forget()
        self._sec_produto.pack_forget()
        self._sec_lote.pack_forget()
        self._row_btns.pack_forget()

        self._chave_entry.focus()

    def _construir_sec_chave(self):
        sec = SecaoFormulario(self._scroll, "1. Ler chave de acesso do DANFE")
        sec.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            sec,
            text="Posicione o cursor abaixo e leia o código de barras do DANFE (44 dígitos). "
                 "O número da NF será extraído automaticamente.",
            font=ctk.CTkFont(size=11), text_color="#5F5E5A",
            anchor="w", justify="left", wraplength=720,
        ).pack(fill="x", padx=14, pady=(0, 8))

        frame = ctk.CTkFrame(sec, fg_color="transparent")
        frame.pack(fill="x", padx=14, pady=(0, 6))
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Chave de acesso (44 dígitos) *",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#888780", anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        row_entry = ctk.CTkFrame(frame, fg_color="transparent")
        row_entry.grid(row=1, column=0, sticky="ew")
        row_entry.grid_columnconfigure(0, weight=1)

        self._chave_entry = ctk.CTkEntry(
            row_entry,
            placeholder_text="Leia o código de barras do DANFE...",
            height=36, font=ctk.CTkFont(size=12),
            fg_color=COR_CINZA_E, border_color=COR_CINZA_B,
        )
        self._chave_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._chave_entry.bind("<Return>", lambda e: self._processar_chave())

        ctk.CTkButton(
            row_entry, text="Validar", width=80, height=36,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=12),
            command=self._processar_chave,
        ).grid(row=0, column=1)

        # Card de confirmação da chave
        self._card_chave = ctk.CTkFrame(
            sec, fg_color=COR_AZUL_L, corner_radius=6,
            border_width=1, border_color=COR_AZUL_M
        )
        self._lbl_nf_info = ctk.CTkLabel(
            self._card_chave, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AZUL, anchor="w"
        )
        self._lbl_nf_info.pack(fill="x", padx=12, pady=8)

    def _construir_sec_scraping(self):
        """Seção de status do scraping — visível durante o processo."""
        self._sec_scraping = ctk.CTkFrame(
            self._scroll, fg_color=COR_AMBER_BG, corner_radius=8,
            border_width=1, border_color="#EF9F27"
        )

        row_top = ctk.CTkFrame(self._sec_scraping, fg_color="transparent")
        row_top.pack(fill="x", padx=14, pady=(12, 4))

        self._lbl_scraping = ctk.CTkLabel(
            row_top, text="Abrindo portal SEFAZ...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AMBER_T, anchor="w"
        )
        self._lbl_scraping.pack(side="left")

        self._btn_cancelar_scrap = ctk.CTkButton(
            row_top, text="Cancelar", width=80, height=26,
            fg_color=COR_BRANCO, text_color=COR_VERM,
            border_width=1, border_color=COR_VERM,
            hover_color=COR_VERM_BG,
            font=ctk.CTkFont(size=11),
            command=self._cancelar_scraping,
        )
        self._btn_cancelar_scrap.pack(side="right")

        self._progress = ctk.CTkProgressBar(
            self._sec_scraping, mode="indeterminate",
            progress_color=COR_AZUL_M
        )
        self._progress.pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkLabel(
            self._sec_scraping,
            text="Resolva o CAPTCHA no browser. O SCE preencherá os campos "
                 "automaticamente após a consulta.",
            font=ctk.CTkFont(size=11), text_color="#5F5E5A",
            anchor="w", justify="left",
        ).pack(fill="x", padx=14, pady=(0, 12))

    def _construir_sec_produto(self):
        self._sec_produto = SecaoFormulario(self._scroll, "2. Identificar produto")

        frame = ctk.CTkFrame(self._sec_produto, fg_color="transparent")
        frame.pack(fill="x", padx=14, pady=(0, 6))
        frame.grid_columnconfigure((0, 1), weight=1)

        self._ean  = CampoBarras(frame, on_leitura=self._on_leitura_ean)
        self._ean.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._nome = CampoNome(frame, on_leitura=self._on_leitura_nome)
        self._nome.grid(row=0, column=1, sticky="ew")

        self._card_produto = ctk.CTkFrame(
            self._sec_produto, fg_color=COR_VERDE_BG,
            corner_radius=6, border_width=1, border_color="#97C459"
        )
        self._lbl_produto = ctk.CTkLabel(
            self._card_produto, text="", text_color=COR_VERDE_T,
            font=ctk.CTkFont(size=12), anchor="w", justify="left"
        )
        self._lbl_produto.pack(anchor="w", padx=12, pady=8)

        # Cadastro rápido inline
        self._frame_rap = ctk.CTkFrame(
            self._sec_produto, fg_color=COR_AMBER_BG, corner_radius=8,
            border_width=1, border_color="#EF9F27"
        )
        ctk.CTkLabel(self._frame_rap,
                     text="Produto não encontrado — cadastro rápido",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_AMBER_T, anchor="w"
                     ).pack(fill="x", padx=14, pady=(10, 0))
        self._lbl_ean_rap = ctk.CTkLabel(
            self._frame_rap, text="", text_color=COR_AZUL,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w"
        )
        self._lbl_ean_rap.pack(fill="x", padx=14, pady=(4, 4))

        g1 = ctk.CTkFrame(self._frame_rap, fg_color="transparent")
        g1.pack(fill="x", padx=14, pady=(0, 4))
        g1.grid_columnconfigure((0, 1, 2), weight=1)
        self._rap_nome    = Campo(g1, "Nome", obrigatorio=True)
        self._rap_nome.grid(row=0, column=0, padx=(0,8), sticky="ew", columnspan=2)

        g2 = ctk.CTkFrame(self._frame_rap, fg_color="transparent")
        g2.pack(fill="x", padx=14, pady=(0, 4))
        g2.grid_columnconfigure((0,1,2), weight=1)
        self._rap_fornecedor= Campo(g2, "Fornecedor", placeholder="Opcional")
        self._rap_fornecedor.grid(row=0, column=1, padx=(0,8), sticky="ew")
        self._rap_marca     = Campo(g2, "Marca", placeholder="Opcional")
        self._rap_marca.grid(row=0, column=1, sticky="ew")

        self._rap_ctl_val= ctk.CTkCheckBox(
            g2, text= "Possui validade/Lote", text_color=COR_AZUL,
            font= ctk.CTkFont(size= 11, weight="bold")
        )
        self._rap_ctl_val.grid(row=0, column= 2, sticky= "e", padx= (0,8))
        self._rap_ctl_val.select()

        row_rap = ctk.CTkFrame(self._frame_rap, fg_color="transparent")
        row_rap.pack(anchor="e", padx=14, pady=(4, 12))
        ctk.CTkButton(row_rap, text="Cancelar", width=90, height=28,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      command=self._cancelar_cadastro_rapido
                      ).pack(side="left", padx=(0,8))
        ctk.CTkButton(row_rap, text="Cadastrar e continuar →", width=190, height=28,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      command=self._executar_cadastro_rapido
                      ).pack(side="left")
        
    def _construir_sec_lote(self):
        self._sec_lote = SecaoFormulario(self._scroll, "3. Dados do lote")

        # Faixa de NF (sempre visível, preenchida automaticamente)
        self._frame_nf_info = ctk.CTkFrame(
            self._sec_lote, fg_color=COR_AZUL_L, corner_radius=6,
            border_width=1, border_color=COR_AZUL_M
        )
        self._frame_nf_info.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(self._frame_nf_info,
                     text="Nota fiscal (extraída automaticamente):",
                     font=ctk.CTkFont(size=11), text_color=COR_AZUL, anchor="w"
                     ).pack(side="left", padx=12, pady=8)
        self._lbl_nf_valor = ctk.CTkLabel(
            self._frame_nf_info, text="—",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AZUL, anchor="w"
        )
        self._lbl_nf_valor.pack(side="left", padx=4)

        # Indicador de preenchimento automático
        self._lbl_auto = ctk.CTkLabel(
            self._sec_lote,
            text="",
            font=ctk.CTkFont(size=11), text_color=COR_VERDE_T,
            fg_color=COR_VERDE_BG, corner_radius=5, anchor="w",
        )

        r1 = ctk.CTkFrame(self._sec_lote, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(0, 6))
        r1.grid_columnconfigure((0, 1), weight=1)
        self._num_lote  = Campo(r1, "Número do lote ", obrigatorio=True,
                                placeholder="Ex: L2024-0512")
        self._num_lote.grid(row=0, column=0, padx=(0,8), sticky="ew")
        self._data_venc = Campo(r1, "Data de vencimento *", obrigatorio=True,
                                placeholder="DD/MM/AAAA")
        self._data_venc.grid(row=0, column=1, sticky="ew")

        r2= ctk.CTkFrame(self._sec_lote,fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(0, 6))
        r2.grid_columnconfigure((0,1), weight=0)
        self._und_lote= Campo(r2, "Unidade de estoque", tipo="select", opcoes=UNIDADES, largura=80)
        self._und_lote.grid(row=0, column=0, padx=(10,8), sticky= "w")
        self._centro= Campo(r2, "Centro de alocação", tipo="select", opcoes=CENTROS, largura= 160)
        self._centro.grid(row=0, column=1, sticky="ew")

        r3 = ctk.CTkFrame(self._sec_lote, fg_color="transparent")
        r3.pack(fill="x", padx=14, pady=(0, 6))
        r3.grid_columnconfigure((0, 1), weight=1)
        self._data_fab  = Campo(r3, "Data de fabricação", placeholder="DD/MM/AAAA")
        self._data_fab.grid(row=0, column=0, padx=(0,8), sticky="ew")
        self._quantidade= Campo(r3, "Quantidade ", obrigatorio=True,
                                tipo="number", placeholder="0")
        self._quantidade.grid(row=0, column=1, sticky="ew")
        self._quantidade._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())

        r4 = ctk.CTkFrame(self._sec_lote, fg_color="transparent")
        r4.pack(fill="x", padx=14, pady=(0, 6))
        r4.grid_columnconfigure(0, weight=1)
        self._valor_unit = Campo(r4, "Valor unitário (R$) *", obrigatorio=True,
                                 tipo="number", placeholder="0,00")
        self._valor_unit.grid(row=0, column=0, padx=(0,8), sticky="ew")
        self._valor_unit._widget.bind("<KeyRelease>", lambda e: self._atualizar_total())

        self._lbl_total = ctk.CTkLabel(
            self._sec_lote, text="Valor total: —",
            text_color=COR_AZUL, font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        )
        self._lbl_total.pack(fill="x", padx=14, pady=(0, 10))

    def _construir_botoes(self):
        self._row_btns = ctk.CTkFrame(self._scroll, fg_color="transparent")
        ctk.CTkButton(self._row_btns, text="Cancelar", width=90, height=34,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      command=lambda: self._on_navigate("entrada_manual")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self._row_btns, text="Registrar entrada", width=160, height=34,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      command=self._salvar
                      ).pack(side="left")
        ctk.CTkButton(self._row_btns, text="pular produto", width=160, height=34,
                      fg_color="#353535", hover_color=COR_CINZA_E,
                      command=self._carregar_proximo_pendente
                      ).pack(side="left")

    # ── Lógica da chave ───────────────────────────────────────────────────────

    def _processar_chave(self):
        chave = self._chave_entry.get().strip().replace(" ", "").replace(".", "").replace("-", "")
        if not chave:
            self._banner.erro("Leia ou informe a chave de acesso.")
            return

        dados = DanfeEntryAssistant.processar_chave(chave)
        if not dados["valida"]:
            self._banner.erro(dados["erro"])
            self._card_chave.pack_forget()
            return

        self._dados_chave = dados
        self._lbl_nf_info.configure(
            text=f"  ✓  NF nº {dados['numero_nf']}  ·  Série {dados['serie']}  ·  "
        )
        self._card_chave.pack(fill="x", padx=14, pady=(0, 8))
        self._lbl_nf_valor.configure(text=dados["numero_nf"])

        self._banner._limpar()
        self._iniciar_scraping()

    # ── Scraping ──────────────────────────────────────────────────────────────

    def _iniciar_scraping(self):
        """Inicia a escuta do servidor local e abre o navegador."""
        self._sec_scraping.pack(fill="x", pady=(0, 8))
        self._progress.start()
        
        self._lbl_scraping.configure(text="Aguardando validação do CAPTCHA no navegador...")

        thread = threading.Thread(
            target=self._executar_scraping,
            daemon=True,
        )
        thread.start()

    def _executar_scraping(self):
        """Roda na thread separada. Chama after() para voltar à thread da GUI."""
        from Modulo_02_estoque.sefaz_receiver import iniciar_escuta_e_abrir_navegador
        
        try:
            # Esta função vai travar aqui até a extensão mandar os dados (ou dar 5 min de timeout)
            resultado = iniciar_escuta_e_abrir_navegador(self._dados_chave["chave"])
            
            # Quando a resposta chegar, voltamos para a interface principal
            def atualizar():
                if self.winfo_exists():
                    self._on_scraping_concluido(resultado)
                    
            self.after(0, atualizar)
            
        except Exception as exc:
            logger.error("Thread de escuta falhou: %s", exc)
            # Retorna um objeto genérico de erro usando a própria classe da tela
            class DadosFalha:
                sucesso = False
                erro = str(exc)
            
            self.after(0, lambda: self._on_scraping_concluido(DadosFalha()) if self.winfo_exists() else None)

    def _atualizar_status_scraping(self, msg: str):
        """Chamado pela thread do scraper — usa after() para ser thread-safe."""
        def atualiza_seguro():
            # Só atualiza a interface se a tela ainda existir (usuário não saiu)
            if self.winfo_exists() and getattr(self, '_lbl_scraping', None) and self._lbl_scraping.winfo_exists():
                self._lbl_scraping.configure(text=msg)
                
        self.after(0, atualiza_seguro)

    def _on_scraping_concluido(self, resultado: DadosSefaz):
        """Chamado na thread da GUI após o scraping terminar."""
        # Impede o crash de TclError: aborta a atualização se a tela já foi fechada
        if not self.winfo_exists():
            return
            
        self._progress.stop()
        self._sec_scraping.pack_forget()

        if resultado.sucesso:
            self._preencher_campos_automaticamente(resultado)
        else:
            logger.warning("Scraping falhou: %s", resultado.erro)
            self._banner.aviso(
                f"Preenchimento automático não disponível: {resultado.erro}\n")

    def _cancelar_scraping(self):
        # A thread do servidor morrerá sozinha no timeout de 5 minutos,
        # apenas fechamos a UI de progresso.
        self._progress.stop()
        self._sec_scraping.pack_forget()

    # ── Preenchimento automático ──────────────────────────────────────────────

    def _preencher_campos_automaticamente(self, dados):
        """Processa a lista da SEFAZ, auto-completa os possíveis e enfileira os pendentes."""
        self._sec_produto.pack(fill="x", pady=(0, 8))
        self._sec_lote.pack(fill="x", pady=(0, 8))
        self._row_btns.pack(anchor="e", pady=(0, 8))

        if dados.numero_nf:
            self._lbl_nf_valor.configure(text=dados.numero_nf)
            self._dados_chave["numero_nf"] = dados.numero_nf

        if dados.data_emissao:
            self._data_fab.set(dados.data_emissao.strftime("%d/%m/%Y"))

        self._emitente_atual = dados.nome_emitente
        self._itens_pendentes = []
        self._resumo_danfe = []  # Histórico para montar a tabela no final
        itens_sucesso = 0
        itens_ignorados = 0

        
        # Loop de processamento em lote
        for item in dados.itens:
            ean_item = str(item.get("ean", "")).strip().upper()
            nome_item= str(item.get("descricao","")).strip()
            prod= None
            try: 
                if ean_item and ean_item!= "SEM GTIN":
                    prod= EstoqueService.buscar_produto_por_ean(ean_item)
                elif nome_item:
                    prod= EstoqueService.buscar_produto_por_nome(nome_item)
            except Exception:
                pass

            
            # Verificação de duplicidade para pular a inserção
            if prod and item.get("lote"):
                try:
                    lotes_existentes = EstoqueService.listar_lotes(prod.id, apenas_com_saldo=False)
                    ja_cadastrado = any(
                        l.num_lote == item["lote"] and l.nota_fiscal == dados.numero_nf 
                        for l in lotes_existentes
                    )
                    
                    if ja_cadastrado:
                        itens_ignorados += 1
                        self._resumo_danfe.append({
                            "descricao": prod.nome,
                            "lote": item["lote"],
                            "qtd": item.get("quantidade", 0),
                            "status": "Ignorado (Já Existia)"
                        })
                        continue 
                except Exception:
                    pass

            self._itens_pendentes.append(item)

        if itens_sucesso > 0:
           self._banner.sucesso(f"{itens_ignorados} itens ignorados pois já estavam registrados.")
            
        if self._itens_pendentes:
                self._banner.aviso(f"Existem {len(self._itens_pendentes)} itens aguardando revisão  e confirmação.")
                self._carregar_proximo_pendente()
        else:
            self._exibir_resumo_danfe()
            
    def _carregar_proximo_pendente(self):
        """Carrega o próximo item"""
        if not hasattr(self, '_itens_pendentes') or not self._itens_pendentes:
            return
            
        item = self._itens_pendentes.pop(0)
        
       
        self._produto_sel = None
        self._card_produto.pack_forget()
        self._frame_rap.pack_forget()
        self._ean.limpar()
        self._nome.limpar()
        # -------------------------------------------------------------------
        
        # Preenche os inputs raspados
        if item.get("lote"): self._num_lote.set(item["lote"])
        if item.get("validade"): self._data_venc.set(item["validade"])
        if item.get("fabricacao"): self._data_fab.set(item["fabricacao"])
        if item.get("quantidade"): self._quantidade.set(str(item["quantidade"]))
        if item.get("valor_unitario"): self._valor_unit.set(str(item["valor_unitario"]).replace(".", ","))
        
        if item.get("unidade_estoque"): 
            unidade_tratada = _mapear_unidade(str(item["unidade_estoque"]))
            self._und_lote.set(unidade_tratada)

        self._atualizar_total()
        
        ean_item= str(item.get("ean", "")).strip().upper()
        nome_item= str(item.get("descricao","")).strip()

        if ean_item and ean_item != "SEM GTIN":
            self._ean.set(ean_item)
            self._on_leitura_ean(ean_item)

            if self._produto_sel is None and nome_item:
                self._rap_nome.set(nome_item)
                try:
                    if getattr(self, "_emitente_atual", None):
                        self._rap_fornecedor.set(self._emitente_atual)
                except Exception: pass

        else:
            if nome_item:
                self._nome.set(nome_item)
                self._on_leitura_nome(nome_item)

                if self._produto_sel is None:
                    self._banner.aviso(f"Produto não encontrado. Realizar cadastro rápido", 10000)

                    self._ean_pendente= None
                    self._lbl_ean_rap.configure(text="Produto sem código de barras")
                    self._rap_nome.set(nome_item)
                    self._frame_rap.pack(fill="x", padx=14, pady=(0,8))
                    
                    try:
                        if getattr(self, "_emitente_atual", None):
                            self._rap_fornecedor.set(self._emitente_atual)
                    except Exception: pass

                    self._rap_nome.focus()
            else:
                self._banner.aviso("Item sem EAN e sem Nome. Identifique manualmente")
                self._nome.focus()

    # ── Produto ───────────────────────────────────────────────────────────────

    def _on_leitura_ean(self, ean: str):
        self._card_produto.pack_forget()
        self._frame_rap.pack_forget()
        self._produto_sel = None
        if not ean.strip():
            return
        try:
            produto = EstoqueService.buscar_produto_por_ean(ean)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return
        if produto:
            self._mostrar_produto(produto)
        else:
            self._ean_pendente = ean
            self._lbl_ean_rap.configure(text=f"  EAN lido: {ean}")
            self._rap_nome.limpar()
            self._frame_rap.pack(fill="x", padx=14, pady=(0, 8))
            self._rap_nome.focus()

    def _on_leitura_nome(self, nome: str):
        self._card_produto.pack_forget()
        self._produto_sel = None
        if not nome.strip():
            return
        try:
            produto = EstoqueService.buscar_produto_por_nome(nome)
        except Exception as exc:
            self._banner.erro(f"Erro ao buscar produto: {exc}")
            return
        if produto:
            self._mostrar_produto(produto)

    def _mostrar_produto(self, produto):
        self._produto_sel = produto
        controla_val= getattr(produto, 'controla_validade', True)
        status_val= "Sim" if controla_val else "Não"

        self._lbl_produto.configure(
            text=(f"  {produto.nome}\n"
                 "·  Fornecedor: {produto.fornecedor or '—'}  ·  "
                  f"Estoque mín.: {produto.estoque_minimo} . Rastreabilidade: {status_val}")
        )
        self._card_produto.pack(fill="x", padx=14, pady=(0, 8))
        self._banner._limpar()
        
        if not controla_val:
            self._num_lote.limpar()
            self._data_venc.limpar()
            self._data_fab.limpar()

            for widget in[self._num_lote, self._data_venc, self._data_fab]:
                widget._widget.configure(state="disabled", fg_color=COR_CINZA_E)
            self._quantidade.focus
        else:
            for widget in [self._num_lote, self._data_venc, self._data_fab]:
                widget._widget.configure(state="normal", fg_color=COR_CINZA_E)
                
            if not self._num_lote.get():
                self._num_lote.focus()
    def _buscar_produto_por_id(self, id_: int):
        p = ProdutoRepo.buscar_por_id(id_)
        if p:
            self._ean.set(p.ean)
            self._on_leitura_ean(p.ean)

    def _executar_cadastro_rapido(self):
        if not self._rap_nome.validar():
            return
        try:
            produto = EstoqueService.criar_produto(
                nome            = self._rap_nome.get().strip(),
                ean             = self._ean_pendente,
                fornecedor      = self._rap_fornecedor.get().strip() or None,
                marca           = self._rap_marca.get().strip() or None,
                controla_validade= bool(self._rap_ctl_val.get())
            )
            self._ean_pendente = None
            self._frame_rap.pack_forget()
            self._mostrar_produto(produto)
            self._banner.sucesso(f"Produto '{produto.nome}' cadastrado.")
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro no cadastro rápido DANFE: %s", exc)
            self._banner.erro(f"Erro ao cadastrar: {exc}")

    def _cancelar_cadastro_rapido(self):
        self._frame_rap.pack_forget()
        self._ean_pendente = None
        self._ean.limpar()
        self._ean.focus()

    # ── Cálculo e persistência ────────────────────────────────────────────────

    def _atualizar_total(self):
        try:
            qtd  = int(self._quantidade.get() or "0")
            vunt = Decimal(self._valor_unit.get().replace(",", ".") or "0")
            self._lbl_total.configure(text=f"Valor total calculado: R$ {qtd * vunt:,.2f}")
        except Exception:
            self._lbl_total.configure(text="Valor total: —")

    def _salvar(self):
        if not self._dados_chave:
            self._banner.erro("Leia e valide a chave de acesso primeiro.")
            return
        if not self._produto_sel:
            self._banner.erro("Identifique o produto pelo código de barras")
            return

        controla_val= getattr(self._produto_sel, 'controla_validade', True)

        campos_gerais= [self._quantidade.validar(), self._valor_unit.validar()]
        if controla_val:
            if not all( campos_gerais+ [self._num_lote.validar(), self._data_venc.validar()]):
                return
        else:
            if not all(campos_gerais):
                return

        data_venc = None
        data_fab= None
        num_lote_final= None

        if controla_val:
            data_venc= _parse_date(self._data_venc.get())
            if not data_venc:
                self._data_venc.erro("Data inválida. Use DD/MM/AAAA.")
                return
            num_lote_final= self._num_lote.get()
            
            if self._data_fab.get():
                data_fab = _parse_date(self._data_fab.get())
            if not data_fab:
                self._data_fab.erro("Data inválida. Use DD/MM/AAAA.")
                return

        
        try:
            vunt = Decimal(self._valor_unit.get().replace(",", "."))
            if vunt <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            self._valor_unit.erro("Informe um valor unitário positivo.")
            return

        # Prevenir erro de banco verificando duplicidade manual 
        if controla_val:
            try:
                lotes_existentes = EstoqueService.listar_lotes(self._produto_sel.id, apenas_com_saldo=False)
                ja_cadastrado = any(
                    l.num_lote == self._num_lote.get() and l.nota_fiscal == self._dados_chave["numero_nf"]
                    for l in lotes_existentes
                )
                if ja_cadastrado:
                    self._banner.erro("Ops! Este lote já foi cadastrado para esta Nota Fiscal.")
                    return
            except Exception:
                pass

        try:
            qtd = int(self._quantidade.get())
            if qtd <= 0:
                raise ValueError()
        except ValueError:
            self._quantidade.erro("Informe um número inteiro positivo.")
            return

        try:
            vunt = Decimal(self._valor_unit.get().replace(",", "."))
            if vunt <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            self._valor_unit.erro("Informe um valor unitário positivo.")
            return

        try:
            EstoqueService.registrar_entrada_danfe(
                produto_id      = self._produto_sel.id,
                num_lote        = self._num_lote.get(),
                nota_fiscal     = self._dados_chave["numero_nf"],
                chave_acesso    = self._dados_chave["chave"],
                unidade_estoque = self._und_lote.get(), 
                centro_alocacao = self._centro.get(),
                data_vencimento = data_venc,
                data_fabricacao = data_fab,
                quantidade      = qtd,
                valor_unitario  = vunt,
                usuario_id      = self._usuario.id,
            )
        except ValueError as exc:
            self._banner.erro(str(exc))
            self._carregar_proximo_pendente()
            return
        except Exception as exc:
            logger.error("Erro ao registrar entrada DANFE: %s", exc)
            self._banner.erro(f"Erro ao registrar: {exc}")
            return

        aviso = ""
        try:
            saldo  = LoteRepo.saldo_total_produto(self._produto_sel.id)
            minimo = self._produto_sel.estoque_minimo
            if minimo > 0 and saldo <= minimo:
                aviso = f" · Atenção: saldo ({saldo}) ≤ mínimo ({minimo})."
        except Exception:
            pass
        
        lote_msg= f"Lote:{num_lote_final}" if controla_val else "Item de consumo(Sem lote)"
        nf = self._dados_chave["numero_nf"]
        self._banner.sucesso(
            f"Entrada DANFE registrada: {qtd} unid. de '{self._produto_sel.nome}' · "
            f"Lote: {lote_msg} · NF: {nf}.{aviso}"
        )

        # 1. Adiciona o item recém processado ao Resumo Final
        if not hasattr(self, '_resumo_danfe'):
            self._resumo_danfe = []
            
        self._resumo_danfe.append({
            "descricao": self._produto_sel.nome,
            "lote": self._num_lote.get(),
            "qtd": qtd,
            "status": "Cadastrado Automaciamente"
        })

        # 2. Limpa os campos após salvar
        for campo in [self._num_lote, self._data_venc, self._data_fab, self._quantidade, self._valor_unit]:
            campo.limpar()
            
        # 3. Puxa o próximo da fila ou exibe o card de resumo
        if hasattr(self, '_itens_pendentes') and self._itens_pendentes:
            self._carregar_proximo_pendente()
        else:
            self._exibir_resumo_danfe()


    def _exibir_resumo_danfe(self):
        """Exibe o card final mostrando a tabela de resumo do que ocorreu nesta NF."""
        # Esconde o formulário ativo
        self._sec_produto.pack_forget()
        self._sec_lote.pack_forget()
        self._row_btns.pack_forget()
        self._banner.sucesso("Leitura e importação da NF-e concluídas com sucesso!")
        
        for w in self._scroll.winfo_children():
            if getattr(w, "_prox_bar", False):
                w.destroy()
                
        card_resumo = ctk.CTkFrame(self._scroll, fg_color=COR_BRANCO, corner_radius=8, border_width=1, border_color=COR_CINZA_B)
        card_resumo._prox_bar = True
        card_resumo.pack(fill="x", pady=(8, 0))
        
        titulo = f"Resumo da Nota Fiscal nº {self._dados_chave['numero_nf']}" if self._dados_chave else "Resumo da Importação"
        ctk.CTkLabel(card_resumo, text=titulo, font=ctk.CTkFont(size=14, weight="bold"), text_color=COR_AZUL, anchor="w").pack(fill="x", padx=16, pady=(16, 8))
        
        # Cria a tabela de resumo
        tabela = ctk.CTkFrame(card_resumo, fg_color="transparent")
        tabela.pack(fill="x", padx=16, pady=(0, 16))
        
        # Cabeçalhos da tabela
        headers = [("Produto / EAN", 350), ("Lote", 150), ("Qtd", 80), ("Status", 200)]
        for col, (texto, largura) in enumerate(headers):
            ctk.CTkLabel(tabela, text=texto, font=ctk.CTkFont(size=11, weight="bold"), text_color="#888780", width=largura, anchor="w").grid(row=0, column=col, padx=4, pady=4, sticky="w")
            
        # Linhas da tabela populadas dinamicamente
        for row, item in enumerate(getattr(self, "_resumo_danfe", [])):
            ctk.CTkLabel(tabela, text=item.get("descricao", "")[:45], font=ctk.CTkFont(size=11), width=350, anchor="w").grid(row=row+1, column=0, padx=4, pady=2, sticky="w")
            ctk.CTkLabel(tabela, text=item.get("lote", ""), font=ctk.CTkFont(size=11), width=150, anchor="w").grid(row=row+1, column=1, padx=4, pady=2, sticky="w")
            ctk.CTkLabel(tabela, text=str(item.get("qtd", "")), font=ctk.CTkFont(size=11), width=80, anchor="w").grid(row=row+1, column=2, padx=4, pady=2, sticky="w")
            
            # Definindo cores conforme o que aconteceu
            status = item.get("status", "")
            if "Ignorado" in status:
                cor = COR_AMBER_T
            elif "Manual" in status:
                cor = COR_AZUL_M
            else:
                cor = COR_VERDE_T
                
            ctk.CTkLabel(tabela, text=status, font=ctk.CTkFont(size=11, weight="bold"), text_color=cor, width=200, anchor="w").grid(row=row+1, column=3, padx=4, pady=2, sticky="w")
            
        # Linha de botões inferior
        row_btns = ctk.CTkFrame(card_resumo, fg_color="transparent")
        row_btns.pack(fill="x", padx=16, pady=(0, 16))
        
        ctk.CTkButton(row_btns, text="Nova Entrada DANFE", width=160, height=34, fg_color=COR_AZUL_M, hover_color="#1a5276", command=self._reiniciar).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row_btns, text="Ir para Produtos", width=120, height=34, fg_color=COR_BRANCO, text_color=COR_AZUL_M, border_width=1, border_color=COR_AZUL_M, command=lambda: self._on_navigate("produtos")).pack(side="right")

    def _reiniciar(self):
        self._dados_chave = None
        self._produto_sel = None
        self._modo_manual = False
        self._chave_entry.delete(0, "end")
        for w in [self._card_chave, self._sec_scraping, self._sec_produto,
                  self._card_produto, self._frame_rap, self._sec_lote,
                  self._row_btns, self._lbl_auto]:
            try:
                w.pack_forget()
            except Exception:
                pass
        for campo in [self._num_lote, self._data_fab, self._data_venc,
                      self._quantidade, self._valor_unit]:
            campo.limpar()
        self._lbl_total.configure(text="Valor total: —")
        
        self._banner._limpar() 
        
        for w in self._scroll.winfo_children():
            if getattr(w, "_prox_bar", False):
                w.destroy()
        self._chave_entry.focus()

    def destroy(self):
        """Destrói a tela de forma limpa."""
        super().destroy()
    
    def limpar_memoria(self):
        """Limpa as listas de scraping, itens pendentes e referências de banco."""
        if hasattr(self, '_produto_sel'):
            self._produto_sel = None
        if hasattr(self, '_dados_chave'):
            self._dados_chave = None
            
        if hasattr(self, '_itens_pendentes') and self._itens_pendentes is not None:
            self._itens_pendentes.clear()
            self._itens_pendentes = None
            
        if hasattr(self, '_resumo_danfe') and self._resumo_danfe is not None:
            self._resumo_danfe.clear()
            self._resumo_danfe = None

# ── Utilitário ────────────────────────────────────────────────────────────────

def _parse_date(texto: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto.strip(), fmt).date()
        except ValueError:
            continue
    return None
