"""
Modulo_1 _autenticação . auth_service.py
Sprint 1- AuthService: autenticação real com banco MySQL com bcrypt
"""

import logging
import bcrypt

from Modulo_06_dados import get_session, Usuario

logger= logging.getLogger(__name__)

class AuthService:
    """
    Serviço de autenticação.
    Consulta a tabela usuario no MySQL e verifica a senha com bcrypt 
    """
    @staticmethod
    def autenticar(login: str,senha:str):
        """
        tenta autenticar o usuário pelo login e senha.
        Retorna objeto Usuario, se não None para credenciais inválidas
        """

        if not login or not senha:
            return None
        
        try:
            with get_session() as session:
                usuario = (
                    session.query(Usuario)
                    .filter(Usuario.login == login, Usuario.ativo == True)
                    .first()
                )
 
                if usuario is None:
                    logger.warning("Usuário não encontrado: '%s'", login)
 
                # Verifica senha com bcrypt
                senha_bytes = senha.encode("utf-8")
                hash_bytes  = usuario.senha_hash.encode("utf-8")
 
                if not bcrypt.checkpw(senha_bytes, hash_bytes):
                    logger.warning("Senha incorreta !!")
                    return None
 
                logger.info("Login efetuado!! '%s'[%s]", login, usuario.perfil.value)
                # Expunge para usar o objeto fora da sessão
                session.expunge(usuario)
                return usuario
 
        except Exception as exc:
            logger.error("Erro ao autenticar usuário '%s': %s", login, exc)
            raise
    
    @staticmethod
    def hash_senha(senha:str)-> str:
        """
        Gera hash bcrypt de uma senha em texto plano.
        Usado no cadastro e na troca de senha.
        """
        return bcrypt.hashpw(senha.encode("utf-8"),bcrypt.gensalt(rounds=12)).decode("utf-8")
    
    @staticmethod
    def verificar_senha(senha: str, hash_armazenado: str)->bool:
        return bcrypt.checkpw(
            senha.encode("utf-8"),
            hash_armazenado.encode("utf-8")
        )
    