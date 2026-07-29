"""
Modulo_04_notificacoes . job_log_repo.py
Repositório de leitura de JobLog (auditoria de jobs agendados/automáticos).
Uso interno do módulo — a GUI consome via NotificacaoService.
"""
import logging
from datetime import datetime

from Modulo_06_dados import get_read_session, JobLog

logger = logging.getLogger(__name__)


class JobLogRepo:

    @staticmethod
    def listar_por_job(job_nome: str, limite: int = 10) -> list[JobLog]:
        with get_read_session() as s:
            itens = (s.query(JobLog)
                     .filter(JobLog.job_nome == job_nome)
                     .order_by(JobLog.executado_em.desc())
                     .limit(limite)
                     .all())
            s.expunge_all()
            return itens

    @staticmethod
    def listar_no_periodo(inicio: datetime, fim: datetime, limite: int = 100) -> list[JobLog]:
        with get_read_session() as s:
            itens = (s.query(JobLog)
                     .filter(JobLog.executado_em.between(inicio, fim))
                     .order_by(JobLog.executado_em.desc())
                     .limit(limite)
                     .all())
            s.expunge_all()
            return itens
