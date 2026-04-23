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

def _mapear_unidaed(unidade_nfe:str)-> str:
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
         row_arq, text="Selecionar arquivo XML ...", width=200, height=34 
         fg_color=COR_BRANCO, text_color="#3d3d3a",
         border_width=1, border_color= COR_CINZA_B, hover_color=COR_CINZA_E,
         command= self._selecionar_arquivo,
      ).pack(side="left")

      self._lbl_arquivo= ctk.CTkLabel(
         row_arq, text="Nenhum arquivo selecionado.",
         text_color="#888780", font= ctk.CTkFont(size=11))
      self._lbl_arquivo.pack(side="left", padx=12)

   #_____seção 2:Prévia(criada aqui, exibida ao carregar)_________________________________________
   