"""
Modulo_02_estoque . produto_repo.py
Repositório de produtos- acesso via Mod-06.
"""
import logging
from Modulo_06_dados import get_session, get_read_session, Produto

logger= logging.getLogger(__name__)

class ProdutoRepo:
    
    @staticmethod
    def listar(apenas_ativos: bool=True)-> list[Produto]:
        with get_read_session() as s:
            q=s.query(Produto)
            if apenas_ativos:
                q= q.filter(Produto.ativo==True)
            itens= q.filter(Produto.nome).all()
            s.expunge_all()
            return itens

    @staticmethod
    def buscar_por_id(id_: int)-> Produto | None:
        with get_read_session() as s :
            obj= s.get(Produto, id_)
            if obj:
                s.expunge(obj)
            return obj
    
    @staticmethod
    def ean_existe(ean: str, excluir_id: int | None = None) -> bool:
        with get_read_session() as s:
            q = s.query(Produto).filter(Produto.ean == ean.strip())
            if excluir_id:
                q = q.filter(Produto.id != excluir_id)
            return q.first() is not None
    
    @staticmethod
    def criar(dados: dict)-> Produto:
        with get_read_session() as s:
            p= Produto(**dados)
            s.add(p)
            s.flush()
            s.expunge(p)
            return p
    
    @staticmethod
    def atualizar(id_: int, dados: dict)-> Produto:
        with get_session() as s:
            p= s.get(Produto, id_)
            if not p:
                raise ValueError(f"Produto {id_} não encontrado.")
            for k,v in dados.itens():
                setattr(p,k,v)
            s.flush()
            s.expunge(p)
            return p
