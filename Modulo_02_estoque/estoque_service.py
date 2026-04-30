"""
Modulo_02_estoque . estoque_service.py
EstoqueService- casos de uso UC-02, UC-03, UC-04 (Sprint 2).
Orquestra ProdutoRepo, FornecedoresRepo  e LoteRepo.
"""
import logging
from datetime import date, datetime
from decimal import Decimal

from Modulo_06_dados import TipoMovimentacaoEnum, CentroAlocacaoEnum,UnidadeEstoqueEnum, get_session, Lote, Movimentacao, get_read_session, Produto
from .produto_repo import ProdutoRepo
from .lote_repo import LoteRepo
from .fefo_selector import FEFOSelector
logger= logging.getLogger(__name__)

class EstoqueService:
    #__________ Fornecedores __________________________________________________________________

    def listar_fornecedores_unicos()->list[str]:
        #Retorna valores únicos de forncedor para sugestões no ComboBox de T-05
        return ProdutoRepo.listar_fornecedore_unicos()
    
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
        fornecedor: str    = None,
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
            fornecedor   = fornecedor,
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
    
    @staticmethod
    def calcular_plano_fefo(produto_id: int, quantidade:int):
        """
        RF-08- calcula e retorna plano de consumo FEFO sem gravar no banco.
        O plano é exibido em T-09 antes da confirmação.
        """
        return FEFOSelector.calcular_plano(produto_id, quantidade)
    
    @staticmethod
    def registrar_retirada(plano, usuario_id: int, observacao: str=None):
        """
        RF-07, RN-08- executa o plano FEFO confirmado.
        grava N movimantações (uma por lote) na mesma transação InnoDB.
        lotes esgotados são zerados atomicamente.

        Args: 
            plano: PlanoConsumo retornado por calular_plano_fefo().
            usuario_id: id do usuário que está executando a retirada.
            observacao: texto opcional replicado em todos os registros(RN-05).

        Raises:
            raise ValueError(
                f"Estoque insuficiente. Quantidade máxima disponível:"
                f" {plano['quantidade_total_disponivel']} unidades."
            )
        """
    
        with get_session() as session:
            for item in plano.itens:
                # Atualiza saldo do lote
                lote= session.get(Lote, item.lote_id)
                if lote is None:
                    raise ValueError(f"Lote {item.lote_id} não encontrado.")
                
                lote.quantidade_atual = item.saldo_restante

                #Registra movimentação de saida
                mov= Movimentacao(
                    lote_id = item.lote_id,
                    usuario_id = usuario_id,
                    tipo= TipoMovimentacaoEnum.saida,
                    quantidade = item.qtd_a_retirar,
                    numero_nf= None,
                    observacao= observacao or None,
                    data_hora= datetime.utcnow(),
                )
                session.add(mov)
            
            logger.info(
                "Retirada registrada: produto_id=%s qtd=%s lotes=%s usuario=%s",
                plano.produto_id, plano.quantidade_pedida, len(plano.itens), usuario_id,
            )

            #verifica estoque minimo apos commit e sinaliza para alerta(RF-13)
            try:
                saldo_pos= LoteRepo.saldo_total_produto(plano.produto_id)
                with get_read_session() as s:
                    prod= s.get(Produto, plano.produto_id)
                    if prod and prod.estoque_minimo> 0 and saldo_pos <= prod.estoque_minimo:
                        logger.warning(
                            "ESTOQUE BAIXO: produto_id = %s saldo= %s minimo= %s",
                            plano.produto_id, saldo_pos, prod.estoque_minimo,
                        )
                        return True # sinaliza estoque baixo para a GUI disparar alerta
            except Exception as exc:
                logger.error("Erro ao verificar estoque minimo pós-retirada: %s", exc)

            return False # estoque ok, sem alerta

    @staticmethod 
    def importar_nfe(dados_nfe, usuario_id: int):
        """
        RF-04, RN-06- Importa NF-e: cria lotes para todos os itens cadastrados.
        atomicidade total: tudo ou nada(uma transação por NF-e).

        Args:
            dados_nfe: DadosNFe com todos os itens .cadastrado==True.
            usuario_id: id do usuário que está realizando a importação.
        
        Raises:
            ValueError: se houver itens não cadastrados.
        """
        if dados_nfe.itens_nao_cadastrados:
            nomes=[f"EAN{i.ean}-{i.descricao}" for i in dados_nfe.itens_nao_cadastrados]
            raise ValueError(
                f"Há{len(nomes)} produto(s) não cadastrado(s)."
                f"Cadastre-os antes de importar: \n"+"\n".join(nomes)
            )
        
        from datetime import date as _date
        lotes_criados= []

        with get_session() as session:
            for item in dados_nfe.itens:
                if not item.produto_id:
                    continue # item sem produto cadastrado, já sinalizado no erro acima

                lote= Lote(
                    produto_id = item.produto_id,
                    num_lote = item.num_lote or f"NFE-{dados_nfe.numero_nf}-{item.numero_item}",
                    nota_fiscal = dados_nfe.numero_nf,
                    data_fabricacao= item.data_fabricacao,
                    data_vencimento= item.data_vencimento or _date(9999,12,31),
                    quantidade_inicial= int(item.quantidade),
                    quantidade_atual= int(item.quantidade),
                    valor_unitario = item.valor_unitario,
                    valor_total= item.valor_total,
                    criado_em= datetime.utcnow(),
                )
                session.add(lote)
                session.flush() # para obter o id do lote criado

                mov= Movimentacao(
                lote_id= lote.id,
                usuario_id= usuario_id,
                tipo = TipoMovimentacaoEnum.entrada_nfe,
                quantidade = int(item.quantidade),
                numero_nf = dados_nfe.numero_nf,
                observacao= f"Importação NF-e{dados_nfe.numero_nf}",
                data_hora= datetime.utcnow(),
                )
                session.add(mov)
                lotes_criados.append(lote.id)
        logger.info(
            "NF-e importada nº %s . %d lotes criados . usuario= %s",
            dados_nfe.numero_nf, len(lotes_criados), usuario_id,
        )

        return lotes_criados
    