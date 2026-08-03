"""
Modulo_03_relatorios . grupo_consumo_repo.py
Repositório de grupos de consumo (agrupamento de produtos por palavra-chave
para o relatório de consumo médio). Uso interno do módulo — a GUI consome
via RelatorioService.
"""
import logging

from Modulo_06_dados import get_session, get_read_session, GrupoConsumo

logger = logging.getLogger(__name__)


class GrupoConsumoRepo:

    @staticmethod
    def listar() -> list[GrupoConsumo]:
        with get_read_session() as s:
            itens = s.query(GrupoConsumo).order_by(GrupoConsumo.id).all()
            s.expunge_all()
            return itens

    @staticmethod
    def buscar_por_nome(nome: str) -> GrupoConsumo | None:
        with get_read_session() as s:
            obj = s.query(GrupoConsumo).filter_by(nome=nome).first()
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def criar(nome: str, termos_chave: str) -> None:
        with get_session() as s:
            s.add(GrupoConsumo(nome=nome, termos_chave=termos_chave))

    @staticmethod
    def atualizar(id_: int, nome: str, termos_chave: str) -> None:
        with get_session() as s:
            grupo = s.get(GrupoConsumo, id_)
            if grupo:
                grupo.nome = nome
                grupo.termos_chave = termos_chave

    @staticmethod
    def remover(id_: int) -> None:
        with get_session() as s:
            grupo = s.get(GrupoConsumo, id_)
            if grupo:
                s.delete(grupo)
