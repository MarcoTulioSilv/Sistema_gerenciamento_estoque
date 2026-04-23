"""
Modulo_02_estoque . nfe_parser.py
Sprint 2B- NFeParser: leitura e validação de XML NF-e padrão SEFAZ 4.0.
Extrai produtos, lotes e dados fiscais para uso em T-08
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from lxml import etree
from Modulo_02_estoque import ProdutoRepo

logger= logging.getLogger(__name__)

#Namespace padrão NF-e SEFAZ 4.0
_NS={"nfe": "http://www.portalfiscal.inf.br/nfe"}

@dataclass
class ItemNFe:
    #representa um item extraido da NF-e
    numero_item:    int
    codigo_produto: str          # código interno do emitente
    ean:            str          # EAN/GTIN — usado para identificar produto no SCE
    descricao:      str
    quantidade:     Decimal
    valor_unitario: Decimal
    valor_total:    Decimal
    unidade:        str
    num_lote:       str = ""
    data_fabricacao:  date | None = None
    data_vencimento:  date | None = None
    # Produto encontrado no banco (preenchido após correspondência por EAN)
    produto_id:     int | None = None
    produto_nome:   str = ""
    cadastrado:     bool = False   # True se EAN existe no SCE


@dataclass
class DadosNFe:
    #dados extraidos de um arquivo XML NF-e.
    numero_nf:      str
    serie:          str
    data_emissao:   date
    cnpj_emitente:  str
    nome_emitente:  str
    itens:          list[ItemNFe] = field(default_factory=list)
    # Erros de parsing (campos ausentes, schema inválido)
    erros:          list[str] = field(default_factory=list)
    
    @property
    def valida(self)->bool:
        return len(self.erros)==0
    
    @property
    def itens_nao_cadastrados(self)-> list[ItemNFe]:
        return[ i for i in self.itens if not i.cadastrado]
    
    @property
    def itens_prontos(self)->list[ItemNFe]:
        return [i for i in self.itens if i.cadastrado]

class NFeParser:
    """
    Faz o parsing de arquivos XML NF-e (SEFAZ 4.0) e retorna DadosNFe.
    Após parsing, chama verificar_produtos() para cruzar EANs com o banco.
    """

    @staticmethod
    def ler_arquivo(caminho: str | Path)-> DadosNFe:
        """
        Lê um arquivo XML e retorna DadosNFe.
        lança fileNotFoundError se o arquivp não existir.
        Lança ValueError se o XML for invalido ou não for uma NF-e.
        """

        caminho= Path(caminho)
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado:{caminho}")
        
        try:
            tree = etree.parse(str(caminho))
            root= tree.getroot()
        except Exception as exc:
            raise ValueError(f"XML inválido ou corrompido:{exc}") from exc
        
        return NFeParser._extrair(root)
    
    @staticmethod
    def ler_conteudo(xml_bytes:bytes)-> DadosNFe:
        #faz parsing de bytes XML- útil para testes.
        try:
            root = etree.fromstring(xml_bytes)
        except Exception as exc:
            raise ValueError(f"XML inválido:{exc}") from exc
        return NFeParser._extrair(root)
    
    @staticmethod
    def _extrair(root)-> DadosNFe:
        erros=[]

        #localizar nfeProcNFe ou nfeProc ou NFe diretamente
        nfe=(
            root.find(".//nfe:NFe",_NS)
            or root.find(".//nfe:nfeProc/nfe:NFe",_NS)
            or root
        )
        infNFe= nfe.find(".//nfe:infNFe",_NS)
        if infNFe is None:
            raise ValueError("Elemento infNFe não encontrado- verifique se é uma NF-e válida")
        
        ide = infNFe.find("nfe:ide",_NS)or {}
        emit= infNFe.find("nfe:emit",_NS) or {}

        #Cabeçalho
        numero_nf    = _txt(ide, "nfe:nNF",   _NS, "")
        serie        = _txt(ide, "nfe:serie",  _NS, "")
        data_str     = _txt(ide, "nfe:dhEmi",  _NS, "") or _txt(ide, "nfe:dEmi", _NS, "")
        cnpj_emit    = _txt(emit,"nfe:CNPJ",   _NS, "")
        nome_emit    = (_txt(emit,"nfe:xFant", _NS, "")
                        or _txt(emit,"nfe:xNome",_NS, ""))
        if not numero_nf:
            erros.append("Número da NF não encontrado no XML.")
        if not data_str:
            erros.append("Data de emissão não encontrada no XML.")

        data_emissao= _parse_data_nfe(data_str) if data_str else date.today()

        #Itens
        itens=[]
        dets= infNFe.findall("nfe:det",_NS)
        if not dets:
            erros.append("Nenhum item (det) encontrado na NF-e")
        
        for det in dets:
            try:
                item= NFeParser._extrair_item(det)
                itens.append(item)
            except Exception as exc:
                num= det.get("nItem","?")
                erros.append(f"Erro no item{num}:{exc}")
        
        dados = DadosNFe(
            numero_nf    = numero_nf,
            serie        = serie,
            data_emissao = data_emissao,
            cnpj_emitente= cnpj_emit,
            nome_emitente= nome_emit,
            itens        = itens,
            erros        = erros,
        )
        logger.info(
            "NF-e lida: nº %s · %d itens · %d erros",
            numero_nf, len(itens), len(erros)
        )
        return dados
    
    def _extrair_item(det)->ItemNFe:
        #Extrai um item det da NF-e
        prod = det.find("nfe:prod",_NS)
        rastro= det.find(".//nfe:rastro",_NS)# rastreabilidade(lote/validade)
        
        if prod is None:
            raise ValueError("Elemento prod ausente")
        
        ean_raw=(_txt(prod,"nfe:cEAN",_NS,"") or _txt(prod,"nfe:cEANTrib",_NS))
        #EANs "SEM GTIN" são invalidos- tratar como ausente

        ean= ean_raw if ean_raw and ean_raw.upper() not in ("SEM GTIN","") else ""

        qtd_str = _txt(prod,"nfe:qCom", _NS,"0")
        vunit_str=_txt(prod,"nfe:vUnCom",_NS,"0")
        vtot_str= _txt(prod,"nfe:vProd",_NS,"0")

        item= ItemNFe(
            numero_item    = int(det.get("nItem", 0)),
            codigo_produto = _txt(prod, "nfe:cProd",  _NS, ""),
            ean            = ean,
            descricao      = _txt(prod, "nfe:xProd",  _NS, ""),
            quantidade     = Decimal(qtd_str.replace(",", ".")),
            valor_unitario = Decimal(vunit_str.replace(",", ".")),
            valor_total    = Decimal(vtot_str.replace(",", ".")),
            unidade        = _txt(prod, "nfe:uCom",   _NS, ""),
        )
        
        #Rastreabilidade(lote/validade)- presente em medicamentos e produtos controlados
        
        if rastro is not None:
            item.num_lote= _txt(rastro,"nfe:nLote",_NS,"")
            fab_str= _txt(rastro,"nfe:dFab",_NS,"")
            val_str= _txt(rastro,"nfe:dVal",_NS,"")
            if fab_str:
                item.data_fabricacao=_parse_data_nfe(fab_str)
            if val_str:
                item.data_vencimento=_parse_data_nfe(val_str)
        
        return item
    
    @staticmethod 
    def verifica_produtos(dados:DadosNFe)->DadosNFe:
        """
        Cruza os EANs dos itens com a tabela produto no banco
        Preenche produto_id, produto_nome e cadastro em cada ItemNFe.
        Chamado após ler_arquivo(), antes de exibir a prévia em T-08
        """
        for item in dados.itens:
            if not item.ean:
                continue
            try:
                produto= ProdutoRepo.buscar_por_ean(item.ean)
                if produto:
                    item.produto_id = produto.id
                    item.produto_nome= produto.nome
                    item.cadastrado= True
            except Exception as exc:
                logger.error("Erro ao verificar EAN'%s:%s", item.ean, exc)
        
        return dados
    
#------------------ Utilitários----------------------------------------------------------------

def _txt(elem, tag:str, ns: dict, default:str="")->str:
    #Retorna o texto de um subelemento ou default se ausente.
    if elem is None:
        return default
    child = elem.find(tag,ns)
    if child is None or child.text is None:
        return default

def _parse_data_nfe(texto:str)-> date:
    """ converte datas no formato NF-e para date.
    Aceita: AAAA-MM-DD, AAAA-MM-DDTHH:MM:SS-03:00, MM/AAA(validade)
    """
    texto= texto.strip()
    # ISO com timezone: 2024-10-01T00:00:00-03:00
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.striptime(texto[:len(fmt)+6],fmt).date()
        except ValueError:
                continue
        #MM/AAAA- validade de medicamentos

    if len(texto)== 7 and "/" in texto:
        mes,ano= texto.split("/")
        return date(int(ano), int (mes),1)
    raise ValueError(f"Formato de data NF-e não reconhecido:'{texto}'")
