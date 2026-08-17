"""
MOD-07 · Modulo_07_patrimonio · documento_baixa_repo.py
Repositório do anexo (PDF) da baixa patrimonial (RF-30, AD-22, v1.8).

Isolado dos demais repos de propósito: o BLOB nunca deve ser carregado por
uma consulta de listagem — só quando o usuário abre o documento.
"""
import logging
from datetime import datetime

from Modulo_06_dados import get_read_session, BaixaBem, BaixaDocumento

logger = logging.getLogger(__name__)


class DocumentoBaixaRepo:

    @staticmethod
    def criar(
        session,
        conteudo: bytes,
        nome_original: str,
        sha256: str,
        tamanho_bytes: int,
        usuario_id: int,
    ) -> BaixaDocumento:
        """
        Insere na MESMA sessão já aberta pelo chamador — participa da
        transação única da baixa (RNF-20): sem documento órfão, sem baixa
        sem anexo.
        """
        documento = BaixaDocumento(
            nome_original=nome_original,
            tamanho_bytes=tamanho_bytes,
            sha256=sha256,
            conteudo=conteudo,
            anexado_em=datetime.utcnow(),
            anexado_por=usuario_id,
        )
        session.add(documento)
        session.flush()  # gera documento.id, usado por baixa_bem.documento_id
        return documento

    @staticmethod
    def buscar_por_bem_id(bem_id: int) -> BaixaDocumento | None:
        # Junta baixa_bem -> baixa_documento por bem_id, carregando o BLOB
        # explicitamente (BaixaBem.documento_pdf é lazy="raise" de propósito).
        with get_read_session() as s:
            baixa = s.query(BaixaBem).filter_by(bem_id=bem_id).first()
            if not baixa:
                return None
            documento = s.get(BaixaDocumento, baixa.documento_id)
            if documento:
                s.expunge(documento)
            return documento
