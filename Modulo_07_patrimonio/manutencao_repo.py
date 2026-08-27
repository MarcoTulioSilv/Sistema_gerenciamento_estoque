"""
MOD-07 · Modulo_07_patrimonio · manutencao_repo.py
Repositório de manutenções realizadas em bens (RF-38, v1.8) — acesso via MOD-06.
"""
import logging
from datetime import date, datetime

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

    @staticmethod
    def buscar_ultima_por_bem(bem_id: int) -> ManutencaoBem | None:
        # Página pública de consulta (RF-37) só precisa da mais recente —
        # evita carregar todo o histórico como listar_por_bem faria.
        with get_read_session() as s:
            item = (s.query(ManutencaoBem)
                    .filter(ManutencaoBem.bem_id == bem_id)
                    .order_by(ManutencaoBem.data_manutencao.desc())
                    .first())
            if item:
                s.expunge(item)
            return item

    @staticmethod
    def listar_periodo(data_ini: date | None = None, data_fim: date | None = None) -> list[ManutencaoBem]:
        """Manutenções de TODOS os bens (T-27, RF-35). Sem datas, devolve tudo."""
        with get_read_session() as s:
            q = s.query(ManutencaoBem).options(
                joinedload(ManutencaoBem.bem), joinedload(ManutencaoBem.usuario)
            )
            if data_ini and data_fim:
                q = q.filter(ManutencaoBem.data_manutencao.between(data_ini, data_fim))
            itens = q.order_by(ManutencaoBem.data_manutencao.desc()).all()
            s.expunge_all()
            return itens
