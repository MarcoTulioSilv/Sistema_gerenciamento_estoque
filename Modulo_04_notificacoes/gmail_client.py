"""
Modulo_04_notificacoes · gmail_client.py
Sprint 4 — GmailClient: envio de e-mail via Gmail SMTP.
App Password armazenado criptografado com Fernet (AES-128) na tabela configuracao.
"""
import logging
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base      import MIMEBase
from email.mime.text      import MIMEText
from email                import encoders
from pathlib              import Path
from Modulo_06_dados import get_read_session, Configuracao 
from cryptography.fernet import Fernet 

logger = logging.getLogger(__name__)

 
class GmailClient:
    """
    Envia e-mails via Gmail SMTP (porta 587, STARTTLS).
    Credenciais lidas da tabela configuracao e descriptografadas com Fernet.
    """
 
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587
 
    @staticmethod
    def _ler_config(chave: str) -> str:
        """Lê um valor da tabela configuracao."""
        
        with get_read_session() as s:
            cfg = s.query(Configuracao).filter_by(chave=chave).first()
            return cfg.valor if cfg else ""
 
    @staticmethod
    def _descriptografar(valor_enc: str) -> str:
        """Descriptografa um valor com a chave Fernet do .env."""
        if not valor_enc:
            return ""
        try:
            
            chave = os.getenv("FERNET_KEY", "").encode()
            if not chave:
                raise ValueError("FERNET_KEY não configurada no .env")
            f = Fernet(chave)
            return f.decrypt(valor_enc.encode()).decode()
        except Exception as exc:
            logger.error("Erro ao descriptografar credencial Gmail: %s", exc)
            raise ValueError(f"Não foi possível descriptografar a senha do Gmail: {exc}") from exc
 
    @classmethod
    def _obter_credenciais(cls) -> tuple[str, str, str]:
        """Retorna (usuario, senha, email_destinatario)."""
        usuario   = cls._ler_config("smtp_usuario")
        senha_enc = cls._ler_config("smtp_senha_enc")
        destino   = cls._ler_config("email_gestora")
        senha     = cls._descriptografar(senha_enc)
        if not usuario or not senha:
            raise ValueError(
                "Gmail não configurado. Acesse Administração → Config. Gmail."
            )
        return usuario, senha, destino
 
    @classmethod
    def enviar(
        cls,
        assunto:    str,
        corpo_html: str,
        anexos:     list[Path] | None = None,
        destinatario: str | None = None,
    ) -> None:
        """
        Envia um e-mail com corpo HTML e anexos opcionais.
 
        Args:
            assunto:      linha de assunto do e-mail.
            corpo_html:   corpo em HTML.
            anexos:       lista de caminhos de arquivo para anexar (ex: XLSX).
            destinatario: sobrescreve o e-mail da gestora se informado.
 
        Raises:
            ValueError: credenciais não configuradas.
            smtplib.SMTPException: falha de envio.
        """
        usuario, senha, destino_padrao = cls._obter_credenciais()
        destino = destinatario or destino_padrao
 
        if not destino:
            raise ValueError(
                "E-mail da gestora não configurado. "
                "Acesse Administração → Config. Gmail."
            )
 
        msg = MIMEMultipart("mixed")
        msg["From"]    = usuario
        msg["To"]      = destino
        msg["Subject"] = assunto
 
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
 
        for caminho in (anexos or []):
            caminho = Path(caminho)
            if not caminho.exists():
                logger.warning("Anexo não encontrado, ignorado: %s", caminho)
                continue
            parte = MIMEBase("application", "octet-stream")
            parte.set_payload(caminho.read_bytes())
            encoders.encode_base64(parte)
            parte.add_header(
                "Content-Disposition",
                f'attachment; filename="{caminho.name}"',
            )
            msg.attach(parte)
 
        logger.info("Enviando e-mail para %s — assunto: %s", destino, assunto)
        with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(usuario, senha)
            smtp.sendmail(usuario, destino, msg.as_bytes())
 
        logger.info("E-mail enviado com sucesso para %s", destino)
 
    @classmethod
    def testar_conexao(cls) -> str:
        """
        Testa a conexão SMTP sem enviar mensagem.
        Retorna mensagem de sucesso ou lança exceção.
        """
        usuario, senha, _ = cls._obter_credenciais()
        with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(usuario, senha)
        return f"Conexão com Gmail estabelecida para {usuario}."
 
    @classmethod
    def criptografar_senha(cls, senha_plain: str) -> str:
        """
        Criptografa uma senha com Fernet para armazenar em configuracao.
        Usado em T-17 ao salvar a App Password.
        """
        chave = os.getenv("FERNET_KEY", "").encode()
        if not chave:
            raise ValueError("FERNET_KEY não configurada no .env")
        return Fernet(chave).encrypt(senha_plain.encode()).decode()
 