"""
Modoulo_02_estoque . fornecedor_repo.py
Repositório de fornecedores- acesso via MOD-06
"""
import logging
from Modulo_06_dados import get_session, get_read_session, Fornecedor, Produto

logger= logging.getLogger(__name__)

class FornecedorRepo:

    @staticmethod
    def listar()-> list[Fornecedor]:
        with get_read_session() as s:
            itens= s.query(Fornecedor).order_by(Fornecedor.nome).all()
            s.expunge_all()
            return itens
    
    @staticmethod
    def buscar_por_id(id_:int)->Fornecedor | None:
        with get_read_session() as s:
            obj= s.get(Fornecedor,id_)
            if obj:
                s.expunge(obj)
                return obj
    
    @staticmethod
    def criar(nome: str)-> Fornecedor:
        with get_session() as s:
            f= Fornecedor(nome= nome.strip())
            s.add(f)
            s.flush()
            s.expunge(f)
            return f
        
    @staticmethod
    def atualizar(id_: int, nome: str)-> Fornecedor:
        with get_session() as s:
            f= s.get(Fornecedor,id_)
            if not f:
                raise ValueError(f"Fornecedor {id_} não encontrado")
            f.nome= nome.strip()
            s.flush()
            s.expunge(f)
            return f 
        
    @ staticmethod
    def contar_produtos(id_: int)-> int:
        with get_read_session() as s:
            return s.query(Produto).filter(Produto.fornecedor_id== id_).count()