"""
Modulo_05_admin · config_service.py
Sprint 6 — ConfigService: leitura e gravação segura de configurações do sistema.

Responsabilidades:
  - CRUD da tabela configuracao (chave-valor).
  - Criptografia/descriptografia do App Password Gmail com Fernet (AD-10).
  - Interface única para T-17 e qualquer outro componente que precise de config.

Chave Fernet:
  Lida da variável de ambiente FERNET_KEY (definida no .env).
  Gerada uma única vez por: python scripts/gerar_chave_fernet.py
"""
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from Modulo_06_dados import get_session, get_read_session, Configuracao
from Modulo_04_notificacoes.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class ConfigService:
    """Gerencia configurações do sistema armazenadas na tabela configuracao."""

    # ── Leitura ───────────────────────────────────────────────────────────────

    @staticmethod
    def get(chave: str) -> str:
        """Retorna o valor da chave, ou string vazia se não existir."""
        with get_read_session() as s:
            cfg = s.query(Configuracao).filter_by(chave=chave).first()
            return cfg.valor if cfg else ""

    @staticmethod
    def listar(prefixo: str | None = None) -> dict[str, str]:
        """
        Retorna dicionário {chave: valor} de todas as configurações.
        Se prefixo for informado, filtra apenas as chaves que começam com ele.
        Nunca retorna 'smtp_senha_enc' descriptografada — use get_smtp_senha().
        """
        with get_read_session() as s:
            q = s.query(Configuracao)
            if prefixo:
                q = q.filter(Configuracao.chave.like(f"{prefixo}%"))
            configs = q.order_by(Configuracao.chave).all()
            return {
                c.chave: c.valor
                for c in configs
                if c.chave != "smtp_senha_enc"  # nunca expõe senha criptografada
            }

    # ── Escrita genérica ──────────────────────────────────────────────────────

    @staticmethod
    def set(chave: str, valor: str, usuario_id: int) -> None:
        """
        Insere ou atualiza uma chave.
        usuario_id é obrigatório para rastreabilidade (RNF-06).

        Raises:
            ValueError: chave ou valor vazio.
        """
        if not chave:
            raise ValueError("Chave não pode ser vazia.")
        if valor is None:
            raise ValueError("Valor não pode ser None.")

        with get_session() as s:
            cfg = s.query(Configuracao).filter_by(chave=chave).first()
            if cfg:
                cfg.valor          = valor
                cfg.atualizado_por = usuario_id
            else:
                s.add(Configuracao(
                    chave          = chave,
                    valor          = valor,
                    atualizado_por = usuario_id,
                ))

        logger.info("Configuração '%s' atualizada por usuario_id=%s", chave, usuario_id)

    # ── Gmail / App Password ──────────────────────────────────────────────────

    @staticmethod
    def salvar_config_gmail(
        smtp_usuario: str,
        app_password: str | None,
        email_destinatario: str,
        usuario_id: int,
    ) -> None:
        """
        Persiste as configurações do Gmail.
        app_password é criptografado com Fernet antes de gravar.
        Se app_password for None ou vazio, a senha existente é mantida.

        Raises:
            ValueError: campos obrigatórios ausentes ou FERNET_KEY não configurada.
        """
        if not smtp_usuario or not smtp_usuario.strip():
            raise ValueError("Endereço Gmail é obrigatório.")
        if not email_destinatario or not email_destinatario.strip():
            raise ValueError("E-mail da gestora é obrigatório.")

        ConfigService.set("smtp_usuario", smtp_usuario.strip(), usuario_id)
        ConfigService.set("email_destinatario_relatorio",
                          email_destinatario.strip(), usuario_id)

        if app_password and app_password.strip():
            senha_enc = ConfigService.criptografar(app_password.strip())
            ConfigService.set("smtp_senha_enc", senha_enc, usuario_id)
            logger.info("App Password Gmail atualizada por usuario_id=%s", usuario_id)

    @staticmethod
    def ler_config_gmail() -> dict[str, str]:
        """
        Retorna as configurações Gmail visíveis (sem a senha descriptografada).
        Formato: {"smtp_usuario": "...", "email_destinatario_relatorio": "..."}
        """
        return {
            "smtp_usuario":                GmailClient._ler_config("smtp_usuario"),
            "email_destinatario_relatorio": GmailClient._ler_config(
                "email_destinatario_relatorio"),
        }

    @staticmethod
    def testar_conexao_gmail() -> str:
        """
        Testa a conexão SMTP sem enviar mensagem.
        Retorna mensagem de sucesso ou lança exceção.
        """
        return GmailClient.testar_conexao()

    # ── Criptografia Fernet ───────────────────────────────────────────────────

    @staticmethod
    def criptografar(texto: str) -> str:
        """
        Criptografa uma string com a chave Fernet do .env (AD-10).

        Raises:
            ValueError: FERNET_KEY não configurada.
        """
        chave = _ler_chave_fernet()
        return Fernet(chave).encrypt(texto.encode("utf-8")).decode("utf-8")

    @staticmethod
    def descriptografar(texto_enc: str) -> str:
        """
        Descriptografa uma string previamente criptografada com Fernet.

        Raises:
            ValueError: chave inválida ou token corrompido.
        """
        chave = _ler_chave_fernet()
        try:
            return Fernet(chave).decrypt(texto_enc.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError(
                "Não foi possível descriptografar o valor. "
                "A chave Fernet pode ter mudado."
            ) from exc


# ── Utilitários internos ──────────────────────────────────────────────────────

def _ler_chave_fernet() -> bytes:
    """Lê FERNET_KEY do ambiente. Lança ValueError se ausente."""
    chave = os.getenv("FERNET_KEY", "").encode("utf-8")
    if not chave:
        raise ValueError(
            "FERNET_KEY não configurada no .env. "
            "Execute: python scripts/gerar_chave_fernet.py"
        )
    return chave
