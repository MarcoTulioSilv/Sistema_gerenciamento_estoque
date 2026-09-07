"""
MOD-07 · Modulo_07_patrimonio · tombo_generator.py
Emissão do número de tombo patrimonial (RF-26), com bloqueio de linha (RN-09).
"""
import logging

from Modulo_06_dados import get_read_session, Configuracao
from .excecoes import MascaraTomboInvalidaError

logger = logging.getLogger(__name__)

_CHAVE_SEQUENCIA = "patrimonio_sequencia"
_CHAVE_MASCARA = "patrimonio_mascara_tombo"


class TomboGenerator:

    @staticmethod
    def aplicar_mascara(mascara: str, seq: int) -> str:
        if "{seq" not in mascara:
            raise MascaraTomboInvalidaError(
                f"Máscara de tombo '{mascara}' não contém o marcador '{{seq}}'."
            )
        try:
            return mascara.format(seq=seq)
        except (KeyError, ValueError) as exc:
            raise MascaraTomboInvalidaError(
                f"Máscara de tombo '{mascara}' é inválida: {exc}"
            ) from exc

    @staticmethod
    def emitir(session) -> str:
        """
        Lê e incrementa patrimonio_sequencia com SELECT ... FOR UPDATE,
        DENTRO da transação já aberta pelo chamador (mesma session do
        cadastro do bem) — garante unicidade entre estações concorrentes.
        """
        cfg_seq = (session.query(Configuracao)
                   .filter_by(chave=_CHAVE_SEQUENCIA)
                   .with_for_update()
                   .first())
        if not cfg_seq:
            raise MascaraTomboInvalidaError(
                f"Configuração '{_CHAVE_SEQUENCIA}' não encontrada. "
                "Rode a migração documentacao/migrations/007-Patrimonio.sql."
            )

        cfg_mascara = session.query(Configuracao).filter_by(chave=_CHAVE_MASCARA).first()
        if not cfg_mascara:
            raise MascaraTomboInvalidaError(
                f"Configuração '{_CHAVE_MASCARA}' não encontrada. "
                "Rode a migração documentacao/migrations/007-Patrimonio.sql."
            )

        proxima_seq = int(cfg_seq.valor) + 1
        tombo = TomboGenerator.aplicar_mascara(cfg_mascara.valor, proxima_seq)

        cfg_seq.valor = str(proxima_seq)
        session.flush()

        logger.info("Tombo emitido: %s", tombo)
        return tombo

    @staticmethod
    def previsualizar() -> str:
        """
        Peek do próximo tombo, sem lock — só para exibição em T-24.
        NÃO reserva o número: se outra estação cadastrar um bem entre a
        exibição e o salvamento real, o número final emitido por emitir()
        (com FOR UPDATE) pode diferir deste preview.
        """
        with get_read_session() as s:
            cfg_seq = s.query(Configuracao).filter_by(chave=_CHAVE_SEQUENCIA).first()
            cfg_mascara = s.query(Configuracao).filter_by(chave=_CHAVE_MASCARA).first()
            if not cfg_seq or not cfg_mascara:
                raise MascaraTomboInvalidaError(
                    "Configuração de tombo não encontrada. "
                    "Rode a migração documentacao/migrations/007-Patrimonio.sql."
                )
            proxima_seq = int(cfg_seq.valor) + 1
            return TomboGenerator.aplicar_mascara(cfg_mascara.valor, proxima_seq)
