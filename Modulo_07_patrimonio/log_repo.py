"""
MOD-07 · Modulo_07_patrimonio · log_repo.py
Repositório do log de auditoria persistido do patrimônio (T-30).
"""
import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from Modulo_06_dados import get_read_session, LogPatrimonio, TipoEventoLogEnum

logger = logging.getLogger(__name__)


class LogRepo:

    @staticmethod
    def registrar(session, tipo_evento: TipoEventoLogEnum, usuario_id: int,
                  descricao: str, bem_id: int | None = None,
                  inventario_id: int | None = None) -> LogPatrimonio:
        """
        Grava uma linha de auditoria na MESMA transação do chamador (mesmo
        padrão de BemRepo.criar/baixar) — nunca abre sessão própria. É essa
        escolha que garante que a operação principal e o registro de
        auditoria nascem ou morrem juntos, nunca um sem o outro.
        """
        evento = LogPatrimonio(
            tipo_evento=tipo_evento, usuario_id=usuario_id,
            descricao=descricao[:255], bem_id=bem_id, inventario_id=inventario_id,
            criado_em=datetime.utcnow(),
        )
        session.add(evento)
        session.flush()
        return evento

    @staticmethod
    def listar_periodo(data_ini: datetime, data_fim: datetime,
                       tipo_evento: TipoEventoLogEnum | None = None,
                       limite: int = 5000) -> list[LogPatrimonio]:
        """
        Limite alto de propósito: LIMIT baixo combinado com ORDER BY DESC
        corta silenciosamente os registros mais ANTIGOS do período sempre
        que o total no intervalo passa do limite (bug real corrigido em
        T-19 nesta mesma sessão) — a paginação em tela cuida da exibição
        gradual, a consulta ao banco não deveria ser o gargalo.
        """
        with get_read_session() as s:
            q = (s.query(LogPatrimonio)
                 .options(joinedload(LogPatrimonio.bem),
                          joinedload(LogPatrimonio.inventario),
                          joinedload(LogPatrimonio.usuario))
                 .filter(LogPatrimonio.criado_em.between(data_ini, data_fim)))
            if tipo_evento is not None:
                q = q.filter(LogPatrimonio.tipo_evento == tipo_evento)
            itens = q.order_by(LogPatrimonio.criado_em.desc()).limit(limite).all()
            s.expunge_all()
            return itens
