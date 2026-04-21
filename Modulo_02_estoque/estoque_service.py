"""
Modulo_02_estoque . estoque_service.py
EstoqueService- casos de uso UC-02, UC-03, UC-04 (Sprint 2).
Orquestra ProdutoRepo, FornecedoresRepo  e LoteRepo.
"""
import logging
from datetime import date
from decimal import Decimal

from Modulo_06_dados import TipoMovimentacaoEnum, CentroAlocacaoEnum,UnidadeEstoqueEnum
from .produto_repo import ProdutoRepo
from .fornecedor_repo import FornecedorRepo
from .lote_repo import LoteRepo

logger= logging.getLogger(__name__)

class EstoqueService:
    #__________ Fornecedores __________________________________________________________________

    @staticmethod
    def listar_fornecedores():
        return FornecedorRepo.listar()
    
    @staticmethod
    def criar_fornecedor(nome: str):
        if not nome or not nome.strip():
            raise ValueError("Nome do fornecedor é obrigatório.")
        return FornecedorRepo.criar(nome)
    
    @staticmethod
    def atualizar_fornecedor(id_: int, nome: str):
        if not nome or not nome.strip():
            raise ValueError("Nome do fornecedor é obrigatório.")
        return FornecedorRepo.atualizar(id_, nome)
    
    #__________ Produtos_________________________________________________________________________
    @staticmethod
    def listar_produtos(apenas_ativos: bool = True):
        return ProdutoRepo.listar(apenas_ativos)
 
    @staticmethod
    def buscar_produto_por_ean(ean: str):
        """Usado pela leitura de código de barras. Retorna None se não encontrado."""
        return ProdutoRepo.buscar_por_ean(ean)
 
    @staticmethod
    def criar_produto(
        nome: str,
        ean: str,
        centro_alocacao: str,
        unidade_estoque: str,
        estoque_minimo: int   = 0,
        descricao: str        = None,
        marca: str            = None,
        fornecedor_id: int    = None,
    ):
        # Validações
        if not nome or not nome.strip():
            raise ValueError("Nome do produto é obrigatório.")
        if not ean or not ean.strip():
            raise ValueError("Código de barras (EAN) é obrigatório.")
        if ProdutoRepo.ean_existe(ean):
            raise ValueError(f"EAN '{ean}' já cadastrado para outro produto.")
        if estoque_minimo < 0:
            raise ValueError("Estoque mínimo não pode ser negativo.")
 
        dados = dict(
            nome            = nome.strip(),
            ean             = ean.strip(),
            centro_alocacao = centro_alocacao,
            unidade_estoque = unidade_estoque,
            estoque_minimo  = estoque_minimo,
            descricao       = descricao.strip() if descricao else None,
            marca           = marca.strip() if marca else None,
            fornecedor_id   = fornecedor_id,
            ativo           = True,
        )
        produto = ProdutoRepo.criar(dados)
        logger.info("Produto criado: %s [EAN %s]", produto.nome, produto.ean)
        return produto
 
    @staticmethod
    def atualizar_produto(id_: int, **campos):
        if "ean" in campos and ProdutoRepo.ean_existe(campos["ean"], excluir_id=id_):
            raise ValueError(f"EAN '{campos['ean']}' já cadastrado para outro produto.")
        if "estoque_minimo" in campos and campos["estoque_minimo"] < 0:
            raise ValueError("Estoque mínimo não pode ser negativo.")
        produto = ProdutoRepo.atualizar(id_, campos)
        logger.info("Produto atualizado: id=%s", id_)
        return produto
    
    #_________ Lotes/ Entradas____________________________________________________________________
    @staticmethod
    def listar_lotes(produto_id: int, apenas_com_saldo: bool = True):
        return LoteRepo.listar_por_produto(produto_id, apenas_com_saldo)
 
    @staticmethod
    def registrar_entrada_manual(
        produto_id:      int,
        num_lote:        str,
        nota_fiscal:     str,
        data_vencimento: date,
        quantidade:      int,
        valor_unitario:  Decimal,
        usuario_id:      int,
        data_fabricacao: date = None,
    ):
        """
        UC-04 — Registrar entrada manual.
        Cria lote + movimentação de entrada na mesma transação (RN-07).
        """
        # Validações — RN-07: NF obrigatória
        if not nota_fiscal or not nota_fiscal.strip():
            raise ValueError("Número da nota fiscal é obrigatório (RN-07).")
        if not num_lote or not num_lote.strip():
            raise ValueError("Número do lote é obrigatório.")
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")
        if valor_unitario <= 0:
            raise ValueError("Valor unitário deve ser maior que zero.")
 
        valor_total = Decimal(str(valor_unitario)) * quantidade
 
        dados = dict(
            produto_id         = produto_id,
            num_lote           = num_lote.strip(),
            nota_fiscal        = nota_fiscal.strip(),
            data_vencimento    = data_vencimento,
            data_fabricacao    = data_fabricacao,
            quantidade_inicial = quantidade,
            quantidade_atual   = quantidade,
            valor_unitario     = Decimal(str(valor_unitario)),
            valor_total        = valor_total,
            usuario_id         = usuario_id,
            tipo               = TipoMovimentacaoEnum.entrada_manual,
        )
        lote = LoteRepo.criar(dados)
        logger.info(
            "Entrada manual registrada: produto_id=%s lote=%s qtd=%s nf=%s",
            produto_id, num_lote, quantidade, nota_fiscal,
        )
        return lote