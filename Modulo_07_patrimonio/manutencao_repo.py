"""
MOD-07 · Modulo_07_patrimonio · manutencao_repo.py
Repositório de manutenções realizadas em bens (RF-38, v1.8) — acesso via MOD-06.
"""
import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from Modulo_06_dados import get_session, get_read_session, ManutencaoBem
from .dto import DadosManutencao

logger = logging.getLogger(__name__)


class ManutencaoRepo:

    @staticmethod
    def criar(bem_id: int, dados: DadosManutencao, usuario_id: int) -> ManutencaoBem:
        # Somente incremental (RN-23): sem UPDATE/DELETE em registro existente,
        # e não toca bem_patrimonial nem movimentacao_bem (AD-24).
        with get_session() as s:
            manutencao = ManutencaoBem(
                bem_id=bem_id,
                data_manutencao=dados.data_manutencao,
                descricao=dados.descricao,
                usuario_id=usuario_id,
                registrado_em=datetime.utcnow(),
            )
            s.add(manutencao)
            s.flush()
            s.expunge(manutencao)
            return manutencao

    @staticmethod
    def listar_por_bem(bem_id: int) -> list[ManutencaoBem]:
        with get_read_session() as s:
            itens = (s.query(ManutencaoBem)
                     .options(joinedload(ManutencaoBem.usuario))
                     .filter(ManutencaoBem.bem_id == bem_id)
                     .order_by(ManutencaoBem.data_manutencao)
                     .all())
            s.expunge_all()
            return itens
