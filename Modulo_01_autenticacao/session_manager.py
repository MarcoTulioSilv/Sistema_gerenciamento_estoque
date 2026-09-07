"""
Modulo_01_autenticacao . session_manager.py
Sprint 1- SessionManager: Mantém o estado da sessão ativa do usuário logado
"""
import logging
from datetime import datetime

logger= logging.getLogger(__name__)

class SessionManager:
    """
    gerencia a sessão do usuário logado.
    Mantém referência ao objeto Usuário e ao timestamp do último acesso.
    Instância única por processo- a GUI é single-process, single-user.
    """
    _usuario_atual = None
    _inicio_sessao: datetime | None = None
    _ultimo_acesso: datetime | None = None

    @classmethod
    def iniciar_sessao(cls,usuario)->None:
        """Registra o início de uma sessão após login bem-sucedido"""
        cls._usuario_atual= usuario
        cls._inicio_sessao= datetime.now()
        cls._ultimo_acesso= datetime.now()
        logger.info("Sessão iniciada: %s[%s]", usuario.login, usuario.perfil.value)

    @classmethod
    def encerrar_sessao(cls)->None:
        if cls._usuario_atual:
            logger.info("Sessão encerrada.")
        cls._usuario_atual = None
        cls._inicio_sessao = None
        cls._ultimo_acesso = None

    @classmethod
    def registrar_atividade(cls)->None:
        cls._ultimo_acesso= datetime.now()
    
    @classmethod
    def get_usuario(cls):
        return cls._usuario_atual 
    
    @classmethod
    def esta_logado(cls)-> bool:
        return cls._usuario_atual is not None
    
    @classmethod
    def get_perfil(cls)->str | None:
        if cls._usuario_atual:
            return cls._usuario_atual.perfil.value
        return None

    @classmethod
    def pode_acessar_patrimonio(cls) -> bool:
        """RF-39/RN-21 — TI sempre acessa; demais perfis exigem permissão explícita."""
        return bool(cls._usuario_atual and cls._usuario_atual.pode_acessar_patrimonio)