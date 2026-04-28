"""
gui · telas · t08_importar_nfe.py
Tela T-08 — Importação de NF-e XML (UC-05, RF-04, RN-06).
 
Fluxo de produtos não cadastrados:
  1. Detecta EANs ausentes no banco após parsing do XML.
  2. Exibe card listando cada produto ausente com seus dados da NF-e.
  3. Oferece duas opções:
     a) Cadastrar automaticamente — pergunta apenas o centro de alocação
        (único campo obrigatório que a NF-e não fornece) e cria os produtos.
     b) Cadastrar manualmente — abre T-05 para preenchimento completo.
  4. Após cadastro (automático ou manual), recarrega a verificação e
     habilita "Confirmar importação" se todos os EANs estiverem cadastrados.
"""

import logging
from tkinter import filedialog

import customtkinter as ctk
from gui.componentes.form_widgets import FeedbackBanner
from Modulo_02_estoque import NFeParser, EstoqueService

logger = logging.getLogger(__name__)

COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_BRANCO  = "#FFFFFF"
COR_VERDE_BG = "#EAF3DE"
COR_VERDE_T  = "#27500A"
COR_AMBER_BG = "#FAEEDA"
COR_AMBER_T  = "#854F0B"
COR_VERM_BG  = "#FCEBEB"
COR_VERM_T   = "#A32D2D"

#Mapeamento de unidades NF-e -> unidadeEstoqueEnum

_unidade_MAP = {
    "CX":  "caixa",  "CXA": "caixa", "caixa": "caixa","C":"caixa","CAIXA":"caixa",
    "PCT": "pacote", "PC":  "pacote", "PACOTE": "pacote", "pacote":"pacote","PCT":"pacote",
    "UN":  "unidade","UND": "unidade","UNID": "unidade","UNIDADE": "unidade","unidade":"unidade",
    "AMP": "ampola", "ampola": "ampola","APL":"ampola","AMPOLA":"ampola",
    "GL":"galao", "galao":"galao", "GALÃO":"galao","GALAO":"galao","galão":"galao",
    "FRD":"fardo","FAR":"fardo", "fardo":"fardo","FARDO":"fardo",
    "LTR": "litro", "LIT":"litro", "litro": "litro","LITRO":"litro",
    "rolo":"rolo","RL":"rolo","RO":"rolo","ROLO":"rolo",
    "KIT":"kit",
    "dose":"dose","DS":"dose","DO":"dose","DOSE":"dose"
}  

def _mapear_unidade(unidade_nfe:str)-> str:
    """ Converte unidade da NF-e para valor do ENUM UnidadeEstoqueEnum
    """
    return _unidade_MAP.get(unidade_nfe.upper().strip(),"UNIDADE")

class TelaImportarNFe(ctk.CTkFrame):
    """ Importação da NF-e com prévia, cadastro automático e confirmação atômica.
    """
    def __init__(self,master,usuario,on_navigate):
      super().__init__(master,fg_color= COR_CINZA_E,corner_radius=0)
      self._usuario  =usuario
      self._on_navigate= on_navigate
      self._dados_nfe= None #DadosNFe após parsing
      self._caminho_atual= None #caminho do arquivo carregado
      self._construir()
   
   #________________CONSTRUÇÂO______________________________________________________________
    def _construir(self):
      topbar= ctk.CTkFrame(self,fg_color=COR_BRANCO,height=44,corner_radius=0)
      topbar.pack(fill="x")
      topbar.pack_propagate(False)
      ctk.CTkLabel(topbar,text="Importação de NF-e", font=ctk.CTkFont(size=13,weight="bold"),
                   text_color=COR_AZUL).pack(side="left",padx=16, pady=10)
      
      self._banner= FeedbackBanner(self)
      self._banner.pack(fill="x",padx=16, pady=(8,0))

      self._scroll_principal= ctk.CTkScrollableFrame(
         self,fg_color=COR_CINZA_E, corner_radius=0)
      self._scroll_principal.pack(fill="both", expand=True)
   
   #___Seção 1: Selecionar arquivo_______________________________________________________________
      sec1= _SecaoCard(self._scroll_principal,titulo="Selecionar arquivo XML")
      sec1.pack(fill="x",padx=16, pady=(12,0))

      row_arq= ctk.CTkFrame(sec1, fg_color="transparent")
      row_arq.pack(fill="x",padx=14, pady=(0,14))

      ctk.CTkButton(
         row_arq, text="Selecionar arquivo XML ...", width=200, height=34,
         fg_color=COR_BRANCO, text_color="#3d3d3a",
         border_width=1, border_color= COR_CINZA_B, hover_color=COR_CINZA_E,
         command= self._selecionar_arquivo,
      ).pack(side="left")

      self._lbl_arquivo= ctk.CTkLabel(
         row_arq, text="Nenhum arquivo selecionado.",
         text_color="#888780", font= ctk.CTkFont(size=11))
      self._lbl_arquivo.pack(side="left", padx=12)

   #_____seção 2:Prévia(criada aqui, exibida ao carregar)_________________________________________
   
      self._sec2= _SecaoCard(self._scroll_principal, titulo="Prévia dos itens da nota")
      
      self._lbl_cabecalho=ctk.CTkLabel(
         self._sec2, text="", text_color="#3d3d3a",
         font=ctk.CTkFont(size=12), justify="left", anchor="w")
      self._lbl_cabecalho.pack(fill="x", padx=14,pady=(0,8))

      self._scroll_itens= ctk.CTkScrollableFrame(
         self._sec2, fg_color=COR_BRANCO, height=200,
         border_width=1, border_color= COR_CINZA_E, corner_radius=0)
      self._scroll_itens.pack(fill="x",padx=14,pady=(0, 8))

   #_________secão 3: Produtos não cadastrados(dinâmica)___________________________________________
      self._sec3= _SecaoCard(
         self._scroll_principal,
         titulo="Produtos não cadastrados",
         cor_borda="#EF9F27", cor_fundo=COR_AMBER_BG)
      
      self._frame_ausentes= ctk.CTkFrame(self._sec3,fg_color="transparent")
      self._frame_ausentes.pack(fill="x",padx=14, pady=(0,8))

      #sub-painel de cadastro automático( oculto até clicar)

      self._frame_auto= ctk.CTkFrame(
         self._sec3, fg_color=COR_CINZA_E,corner_radius=6,
         border_width=1, border_color=COR_CINZA_B)
      
      ctk.CTkLabel(self._frame_auto,
                   text="Centro de alocação para os produtos a cadastrar",
                   text_color="#3d3d3a",
                   font=ctk.CTkFont(size=11, weight="bold"),
                   anchor="w").pack(fill="x", padx=12, pady=(10,4))
      self._opt_centro= ctk.CTkOptionMenu(
         self._frame_auto,
         values=["almoxarifado","farmacia"],
         width=200, height=32, corner_radius=6,
         fg_color= COR_BRANCO, button_color= COR_AZUL_M, text_color="#3d3d3a")
      self._opt_centro.pack(anchor="w", padx=12)

      ctk.CTkLabel(
         self._frame_auto,
         text="Os demais campos poderão ser completados depois em Produtos-> editar",
         text_color="#888780", font=ctk.CTkFont(size=10),
         justify="left", anchor="w").pack(fill="x",padx=12, pady=(4,6))
      
      row_auto_btns= ctk.CTkFrame(self._frame_auto, fg_color="transparent")
      row_auto_btns.pack(anchor="e", padx=12, pady=(0,10))
      ctk.CTkButton(row_auto_btns, text="Cancelar", width=90,height=28,
                    fg_color=COR_BRANCO, text_color="#3d3d3a",
                    border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                    font=ctk.CTkFont(size=11),
                    command=self._ocultar_painel_auto,
                    ).pack(side="left",padx=(0,8))
      ctk.CTkButton(
         row_auto_btns,text="Cadastrar agora", width=140, height=28,
         fg_color=COR_AZUL_M, hover_color="#1a5276",
         font=ctk.CTkFont(size=11),
         command= self._executar_cadastro_automatico,
         ).pack(side="left")
      
      #Botões seção 3
      row_s3_btns= ctk.CTkFrame(self._sec3, fg_color="transparent")
      row_s3_btns.pack(anchor="w", padx=14,pady=(0,12))

      self._btn_auto= ctk.CTkButton(
         row_s3_btns,
         text="Cadastrar automaticamente via NF-e",
         width=260, height=32,
         fg_color=COR_AZUL_M, hover_color="#1a5276",
         font= ctk.CTkFont(size=12),
         command= self._mostrar_painel_auto)
      self._btn_auto.pack(side="left",padx=(0,10))

      ctk.CTkButton(
         row_s3_btns,
         text="Cadastrar manualmente",
         width=180, height=32,
         fg_color= COR_BRANCO, text_color="#3d3d3a",
         border_width=1, border_color=COR_CINZA_B, hover_color= COR_CINZA_E,
         font=ctk.CTkFont(size=12),
         command= lambda: self._on_navigate("novo_produto"),
      ).pack(side="left")

      #seção 4: Botões finais----------------------------------------------------

      self._sec4= ctk.CTkFrame(
         self._scroll_principal, fg_color="transparent")
      ctk.CTkButton(
         self._sec4, text="Cancelar", width=100, height=34,
         fg_color=COR_BRANCO, text_color="#3d3d3a",
         border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
         command= lambda: self._on_navigate("entrada_manual"),
      ).pack(side="left", padx=(0,8))

      self._btn_confirmar=ctk.CTkButton(
         self._sec4, text="Confirma importação", width=180,height=34,
         fg_color= COR_AZUL_M, hover_color="#1a5276",
         state="disabled",
         command=self._confirmar_importacao)
      self._btn_confirmar.pack(side="left")
   #_____________________Arquivo_______________________________________________________
    def _selecionar_arquivo(self):
      caminho= filedialog.askopenfilename(
         title="Selecionar NF-e XML",
         filetypes=[("Arquivo XML","*.xml"), ("todos os arquivos","*.*")],)
      if not caminho:
         return
      self._caminho_atual= caminho
      self._lbl_arquivo.configure(text=caminho.split("/")[-1].split("\\"[-1]))
      self._carregar_nfe(caminho)

    def _carregar_nfe(self, caminho:str):
       # Faz parsing do XML e exibe a prévia.
       try:
          dados= NFeParser.ler_arquivo(caminho)
          dados= NFeParser.verifica_produtos(dados)
          self._dados_nfe=dados
       except Exception as exc:
          self._banner.erro(f"Erro ao ler XML:{exc}")
          return
      
       if dados.erros:
          self._banner.erro("XML com advertência: "+"|". join(dados.erros))

       self._exibir_previa(dados)

    def _recarregar_verificacao(self):
       #Após cadastro automático, re-verifica EANs sem reler o arquivo
       if not self._dados_nfe:
          return
       try:
          self._dados_nfe= NFeParser.verifica_produtos(self._dados_nfe)
       except Exception as exc:
          self._banner.erro(f"Erro ao verificar produtos: {exc}")
          return
       self._exibir_previa(self._dados_nfe)

   #____________Prévia________________________________________________________________
    def _exibir_previa(self, dados):
       #Renderiza cabeçalho, tabela de itens, seção de ausentes e botões.
       
       #Cabeçalho da nota
       self._lbl_cabecalho.configure(
          text=(f"NF-e  nº{dados.numero_nf} . Série {dados.serie} ."
                f"Emissão:{dados.data_emissao.strftime('%d/%m/%Y')}\n"
                f"Emitente:{dados.nome_emitente} . CNPJ: {dados.cnpj_emitente}")
       )

       #tabela de itens
       for w in self._scroll_itens.winfo_children():
          w.destroy()

       hdr= ctk.CTkFrame(self._scroll_itens, fg_color="#FAFAF8", corner_radius=0)
       hdr.pack(fill="x")
       for col, (txt, larg) in enumerate([
           ("#", 30), ("Descrição", 240), ("EAN", 130),
            ("Qtd", 60), ("V.Unit", 80), ("Lote", 100),
            ("Vencimento", 100), ("Status", 120),
       ]):
         ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                      font= ctk.CTkFont(size=9, weight="bold"),
                      weidth= larg, anchor="w",
                      ).grid(row=0, column=col, padx=6, pady=4, sticky="w")
       for i, item in enumerate(dados.itens):
          bg=COR_BRANCO if i%2==0 else "#97DCF8"
          row=ctk.CTkFrame(self._scroll_itens, fg_color=bg, corner_radius=0)
          row.pack(fill="x")
          st_txt="Cadastrado" if item.cadastrado else "Não cadastrado"
          st_bg= COR_VERDE_BG if item.cadastrado else COR_VERM_BG
          st_tc= COR_VERDE_T if item.cadastrado else COR_VERM_T
          venc   = item.data_vencimento.strftime("%d/%m/%Y") \
                     if item.data_vencimento else "—"
          for col, (val, larg) in enumerate([
               (str(item.numero_item), 30),
               (item.descricao[:28], 240),
               (item.ean or "—", 130),
               (str(item.quantidade), 60),
               (f"R${item.valor_unitario:.2f}", 80),
               (item.num_lote or "—", 100),
               (venc, 100),
          ]):
               ctk.CTkLabel(row, text=val, text_color="#3d3d3a",
                            font= ctk.CTkFont(size=11), width= larg,
                            anchor="w").grid(
                               row=0, column= col, padx=6, pady=5, sticky="w")
               ctk.CTkLabel(row, text=st_txt, fg_color=st_bg, text_color= st_tc,
                            font=ctk.CTkFont(size=9,weight="bold"), 
                            corner_radius=6, padx=6, pady=2, width=120,
                            ).grid(row=0, column=7, padx=6, pady=5, sticky="w")
       self._sec2.pack(fill="x", padx=16,pady=(10,0))

       #seção de produtos não cadastrados
       nao_cad= dados.itens_nao_cadastrados
       if nao_cad:
         self._renderizar_ausentes(nao_cad)
         self._sec3.pack(fill="x", padx=16, pady=(10, 0))
         self._sec4.pack(anchor="e", padx=16, pady=14)
         self._btn_confirmar.configure(state="disabled")
       else:
         self._sec3.pack_forget()
         self._frame_auto.pack_forget()
         self._sec4.pack(anchor="e", padx=16, pady=14)
         self._btn_confirmar.configure(state="normal")
   
    def _renderizar_ausentes(self, nao_cad):
       #Exibe a lista de produtos não cadastrados com dados da NF-e
       for w in self._frame_ausentes.winfo_children():
          w.destroy()
      
       ctk.CTkLabel(
          self._frame_ausentes,
          text=(f"{len(nao_cad)} produto(s) não encontrado(s) no cadastro.\n"
                f"A nota não pode ser importada parcialmente (RN-06).\n"
                f"Escolha uma das opções abaixo:"),
                text_color=COR_AMBER_T,
                font=ctk.CTkFont(size=11),
                justify="left", anchor="w",
       ).pack(fill="x", pady=(0,8))

       # Card por produto ausente
       for item in nao_cad:
         card= ctk.CTkFrame(
            self._frame_ausentes, fg_color=COR_BRANCO,
            corner_radius=6, border_width=1, border_color=COR_CINZA_B)
         card.pack(fill="x", pady=3)

         #linha superior: descrição + EAN
         ctk.CTkLabel(
            card,
            text=f"{item.desicao}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COR_AZUL, anchor="w",            
         ).pack(fill="x", padx=10, pady=(8,0))

         #linha inferior: dados disponíveis na NF-e
         dados_txt=(
                f"  EAN: {item.ean or 'ausente'}  ·  "
                f"Qtd NF-e: {item.quantidade} {item.unidade}  ·  "
                f"V.Unit: R${item.valor_unitario:.2f}  ·  "
                f"Lote NF-e: {item.num_lote or '—'}  ·  "
                f"Unidade mapeada: {_mapear_unidade(item.unidade)}"   
         )
         ctk.CTkLabel(
            card, text=dados_txt,
            font=ctk.CTkFont(size=10), text_color="#888780",
            anchor="w", justify="left",
         ).pack(fill="x", pack=10, pady=(2,8))
       ctk.CTkLabel(
          self._frame_ausentes,

          text="ℹ  Campos preenchidos automaticamente: nome, EAN, unidade de estoque.\n"
                 "    Campos que precisarão ser revisados depois: marca, fornecedor, estoque mínimo.",
                 text_color="#888780", font= ctk.CTkFont(size=10),
                 justify="left", anchor="w",
       ).pack(fill="x", pady=(0,6))
   
   #____ Casdastro automático________________________________________________________________________________
   # Exibe o sub-painel para escolher o centro de alocação.
    def _mostrar_painel_auto(self):
       self._frame_auto.pack(fill="x", padx=14, pady=(0,10),
                             before= self._frame_ausentes)
       self._btn_auto.configure(state="disabçed")
      
    def _ocultar_painel_auto(self):
       self._frame_auto.pack_forget()
       self._btn_auto.configure(state="normal")

    def _executar_cadastro_automatico(self):
       """ 
       Cadastra automaticamente todos os produtos não cadastrados
       usadando os  dados extraidos da NF-e.
       Único campo solicitado ao usuário: centro de alocação
       """
       if not self._dados_nfe:
          return
       centro_valor= self._opt_centro.get().lower() #"almoxaridado" ou "farmacia"
       nao_cad= self._dados_nfe.itens_nao_cadastrados
       
       if not nao_cad:
          self._ocultar_painel_auto()
          return
       
       erros=[]
       criados=[]

       try:
       
         for item in nao_cad:
            if not item.ean:
               erros.append(f"'{item.descricao}' sem EAN- cadastre manualmente.")
               continue
            try:
               EstoqueService.criar_produto(
                     nome            = item.descricao[:120],
                     ean             = item.ean,
                     centro_alocacao = centro_valor,
                     unidade_estoque = _mapear_unidade(item.unidade),
                     estoque_minimo  = 0,
                     descricao       = None,
                     marca           = None,
                     fornecedor_id   = None,
               )
               criados.append(item.descricao)
               logger.info("Produto cadastrado automaticamente via NF-e: %s [%s]",
                              item.descricao, item.ean)
            except ValueError as exc:
               #EAN já existe- pode ter sido cadastrado entre a leitura e agora
               erros.append(f"{item.descricao}:{exc}")
            except Exception as exc:
               logger.error("Erro ao cadastrar '%s': %s", item.descricao, exc)
               erros.append(f"'{item.descricao}': erro inesperado-{exc}")
       except ImportError as exc:
          logger.error("Erro inesperado no cadastro automático: %s", exc)
          self._banner.erro("Erro inesperado: {exc}")
          return         
       
      #Feedback
       if criados:
          msg=f"{len(criados)} produtos(s) cadastrado(s): "+",".join(criados[:3])
          if len(criados)>3:
             msg+= f"e mais {len(criados)-3}."
             self._banner.sucesso(msg)
       if erros:
          self._banner.erro("Atenção: "+ "|".join(erros))
       self._ocultar_painel_auto()

       #Recarrega verificação e atualiza a prévia
       self._recarregar_verificacao()

   #____ Importação_____________________________________________________________________

    def _confirmar_importacao(self):
       if not self._dados_nfe:
          return
       if self._dados_nfe.itens_nao_cadastrados:
          self._banner.erro(
             "Ainda há produtos não cadastrados."
             "use 'Cadastrar automaticamente' ou 'Cadastrar manualmente' antes de confirmar.")
          return
       
       try:
          lotes=EstoqueService.importar_nfe(self._dados_nfe, self._usuario.id)
          self._banner.sucesso(
             f"NF-e{self._dados_nfe.numero_nf} importada com sucesso-"
             f"{len(lotes)} lote(s) criado(s)."
          )
          #Resetar tela
          self._dados_nfe= None
          self._caminho_atual= None
          self._lbl_arquivo.configure(text="Nenhum arquivo selecionado.")
          self._sec2.pack_forget()
          self._sec3.pack_forget()
          self._sec4.pack_forget()
          self._btn_confirmar.configure(state="disabled")

       except ValueError as exc:
          self._banner.erro(str(exc))
       except Exception as exc: 
          logger.error("Erro ao importar NF-e: %s", exc)
          self._banner.erro(f"Erro ao importar:{exc}")

#___________Componente auxiliar__________________________________________________________________

class _SecaoCard(ctk.CTkFrame):
   #Card com titulo e linha divisória- padrão das seções do formulário

   def __init__(self, master, titulo:str,
                cor_borda: str=None, cor_fundo: str= COR_BRANCO, **kwargs):
      borda= cor_borda or  "#E8E6DE"
      super().__init__(master, fg_color=cor_fundo, corner_radius=8, 
                       border_width=1, border_color=borda, **kwargs)
      ctk.CTkLabel(self, text=titulo,
                   font=ctk.CTkFont(size=12,weight="bold"),
                   text_color=COR_AZUL).pack(anchor="w", padx=14, pady=(12,0))
      ctk.CTkFrame(self, fg_color="#E8E6DE", height=1).pack(fill="x", padx=14, pady=(6,10))