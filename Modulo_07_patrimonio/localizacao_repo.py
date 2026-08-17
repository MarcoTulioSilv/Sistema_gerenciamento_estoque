"""
MOD-07 · Modulo_07_patrimonio · localizacao_repo.py
Repositório de localizações — acesso via MOD-06.
"""
import logging

from sqlalchemy import func

from Modulo_06_dados import get_session, get_read_session, Localizacao, BemPatrimonial, SituacaoBemEnum

logger = logging.getLogger(__name__)


class LocalizacaoRepo:

    @staticmethod
    def listar(apenas_ativas: bool = True) -> list[Localizacao]:
        with get_read_session() as s:
            q = s.query(Localizacao).order_by(Localizacao.setor, Localizacao.sala)
            if apenas_ativas:
                q = q.filter(Localizacao.ativo == True)
            itens = q.all()
            s.expunge_all()
            return itens

    @staticmethod
    def buscar_por_id(id_: int) -> Localizacao | None:
        with get_read_session() as s:
            obj = s.get(Localizacao, id_)
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def criar(setor: str, sala: str, descricao: str | None = None) -> Localizacao:
        with get_session() as s:
            loc = Localizacao(setor=setor, sala=sala, descricao=descricao)
            s.add(loc)
            s.flush()
            s.expunge(loc)
            return loc

    @staticmethod
    def editar(localizacao_id: int, setor: str, sala: str, descricao: str | None = None) -> Localizacao:
        with get_session() as s:
            loc = s.get(Localizacao, localizacao_id)
            if not loc:
                return None
            loc.setor = setor
            loc.sala = sala
            loc.descricao = descricao
            s.flush()
            s.expunge(loc)
            return loc

    @staticmethod
    def desativar(localizacao_id: int) -> None:
        with get_session() as s:
            loc = s.get(Localizacao, localizacao_id)
            if loc:
                loc.ativo = False

    @staticmethod
    def contar_bens_ativos(localizacao_id: int) -> int:
        # Usado pela RN-10 antes de desativar uma localização.
        with get_read_session() as s:
            return (s.query(BemPatrimonial)
                    .filter(BemPatrimonial.localizacao_id == localizacao_id,
                            BemPatrimonial.situacao == SituacaoBemEnum.ativo)
                    .count())

    @staticmethod
    def listar_com_contagem_bens(apenas_ativas: bool = True) -> list[tuple[Localizacao, int]]:
        """
        Localizações + contagem de bens ativos lotados, em consulta única
        (T-28) — evita N+1 de chamar contar_bens_ativos por linha.
        """
        with get_read_session() as s:
            contagem = (
                s.query(
                    BemPatrimonial.localizacao_id.label("localizacao_id"),
                    func.count(BemPatrimonial.id).label("total"),
                )
                .filter(BemPatrimonial.situacao == SituacaoBemEnum.ativo)
                .group_by(BemPatrimonial.localizacao_id)
                .subquery()
            )

            q = (s.query(Localizacao, func.coalesce(contagem.c.total, 0))
                 .outerjoin(contagem, contagem.c.localizacao_id == Localizacao.id)
                 .order_by(Localizacao.setor, Localizacao.sala))
            if apenas_ativas:
                q = q.filter(Localizacao.ativo == True)

            linhas = q.all()
            for loc, _ in linhas:
                s.expunge(loc)
            return [(loc, total) for loc, total in linhas]
