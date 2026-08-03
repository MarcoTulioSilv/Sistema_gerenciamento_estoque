"""
Modulo_02_estoque . lote_repo.py
Repositório de lotes e movimentações- acesso via MOD-06
"""
import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from Modulo_06_dados import get_session, get_read_session, Lote, Movimentacao, Produto, TipoMovimentacaoEnum

logger= logging.getLogger(__name__)
 
class LoteRepo:

    @staticmethod
    def listar_por_produto(produto_id: int, apenas_com_saldo: bool= True)-> list[Lote]:
        with get_read_session() as s:
            q= (s.query(Lote)
                .filter(Lote.produto_id==produto_id)
                .order_by(Lote.data_vencimento))
            if apenas_com_saldo:
                q= q.filter(Lote.quantidade_atual>0)
            itens= q.all()
            s.expunge_all()
            return itens
    
    def listar_por_produto_consumo(produto_id: int, apenas_com_saldo: bool= True)-> list[Lote]:
        with get_read_session() as s:
            q= (s.query(Lote)
                .filter(Lote.produto_id==produto_id)
                .order_by(Lote.centro_alocacao))
            if apenas_com_saldo:
                q= q.filter(Lote.quantidade_atual>0)
            itens= q.all()
            s.expunge_all()
            return itens
    @staticmethod
    def buscar_por_id(id_: int)-> Lote | None:
        with get_read_session() as s:
            obj= s.get(Lote,id_)
            if obj:
                s.expunge(obj)
            return obj
    
    @staticmethod
    def criar(dados: dict)->Lote:
        #Cria lote e registra movimentação de entrada na mesma transação.
        usuario_id= dados.pop ("usuario_id")
        tipo      = dados.pop("tipo", TipoMovimentacaoEnum.entrada_manual)
        numero_nf = dados.get("nota_fiscal","")

        with get_session() as s:
            lote= Lote(**dados)
            s.add(lote)
            s.flush() # gera lote.id

            mov= Movimentacao(
                lote_id     = lote.id,
                usuario_id  = usuario_id,
                tipo        = tipo,
                quantidade  = lote.quantidade_inicial,
                numero_nf   = numero_nf,
                data_hora   = datetime.utcnow(),
            )
            s.add(mov)
            s.flush()
            s.expunge(lote)
            return lote

    @staticmethod
    def listar_todos_ativos(
        apenas_com_saldo: bool = True,
        produto_id: int | None = None,
        apenas_produtos_ativos: bool = False,
    ) -> list[Lote]:
        # Cross-produto: todos os lotes (com produto já carregado), usado por telas
        # de painel/dashboard/posição de estoque para evitar N+1 de lazy-load.
        with get_read_session() as s:
            q = (s.query(Lote)
                 .join(Produto)
                 .options(joinedload(Lote.produto))
                 .order_by(Produto.nome, Lote.data_vencimento))
            if apenas_com_saldo:
                q = q.filter(Lote.quantidade_atual > 0)
            if produto_id is not None:
                q = q.filter(Lote.produto_id == produto_id)
            if apenas_produtos_ativos:
                q = q.filter(Produto.ativo == True)
            itens = q.all()
            s.expunge_all()
            return itens

    @staticmethod
    def saldo_total_produto(produto_id: int)-> int:
        #Soma do saldo de todos os lotes ativos(Não vencidos) de um produto.
        hoje= date.today()
        with get_read_session() as s:
            lotes=(s.query(Lote)
                   .filter(
                       Lote.produto_id== produto_id,
                       Lote.quantidade_atual>0,
                       Lote.data_vencimento>=hoje,
                   ).all())
            return sum(l.quantidade_atual for l in lotes)

class MovimentacaoRepo:

    @staticmethod
    def listar_recentes(limite: int =50)-> list[Movimentacao]:
        with get_read_session() as s:
            itens = (s.query(Movimentacao)
                     .order_by(Movimentacao.data_hora.desc())
                     .limit(limite).all())
            s.expunge_all()
            return itens

    @staticmethod
    def contar_desde(momento: datetime) -> int:
        with get_read_session() as s:
            return (s.query(func.count(Movimentacao.id))
                    .filter(Movimentacao.data_hora >= momento)
                    .scalar() or 0)

    @staticmethod
    def listar_no_periodo(inicio: datetime, fim: datetime, limite: int = 500) -> list[Movimentacao]:
        with get_read_session() as s:
            itens = (s.query(Movimentacao)
                     .options(
                         joinedload(Movimentacao.usuario),
                         joinedload(Movimentacao.lote).joinedload(Lote.produto),
                     )
                     .filter(Movimentacao.data_hora.between(inicio, fim))
                     .order_by(Movimentacao.data_hora.desc())
                     .limit(limite)
                     .all())
            s.expunge_all()
            return itens