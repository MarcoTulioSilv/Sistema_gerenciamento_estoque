"""MOD-06 - Dados - database.py
   Configuração do engine SQLAlchemy e pool de conexões MySQL.
   unico ponto de acesso ao banco de dados no sistema (baseado na DAS V1.2 - regra MOD-06).
"""

import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis de ambiente do .env
logger= logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos ORM."""
    pass


def _build_url()-> str:
    """Constrói a URL de conexão com base nas variáveis de ambiente."""
    host     = os.getenv("DB_HOST", "127.0.0.1")
    port     = os.getenv("DB_PORT", "3306")
    name     = os.getenv("DB_NAME", "sce_db")
    user     = os.getenv("DB_USER", "sce_app")
    password = os.getenv("DB_PASSWORD", "")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"

def create_db_engine():
    """Cria e retorna o engine SQLAlchemy com pool de conexões configurado."""
    url= _build_url()
    engine= create_engine(
        url,
        poolclass=QueuePool,
        pool_size=int(os.getenv("DB_POOL_SIZE", 5)),
        max_overflow=10,
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 3600)),
        pool_pre_ping=True,  # Verifica conexões antes de usar(detecta quedas de rede)
        echo=os.getenv("APP_DEBUG", "false").lower() == "true",
    )

    #Garante utf8mb4 e fuso UTC em cada nova conexão
    @event.listens_for(engine, "connect")
    def set_connection_defaults(dbapi_conn, _):
        cursor= dbapi_conn.cursor()
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("SET time_zone = '+00:00'")
        cursor.close()
    return engine

#Instâmncia global - criada uma vezna inicialização da aplicação
_engine= None
_SessionLocal= None

def init_db():
    """
    Inicialoza o engine e o pool de sessões.
    Deve ser chamado uma única vez em main.py antes de qualquer operação.
    Lança ConnectionError se não conseguir conectar ao banco.
    """
    global _engine, _SessionLocal
    _engine= create_db_engine()
    _SessionLocal= sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    #Testa conexão imediatamente
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Conexão com o banco de dados estabelecida com sucesso.")
    except Exception as exc:
        logger.critical("Falha ao conectar ao banco de dados: %s", exc)
        raise ConnectionError(
            f"Não foi possível conectar ao banco de dados.\n"
            f"Verifique o arquivo .env e se o MySQL está rodando.\n"
            f"Detalhe: {exc}"
        ) from exc
    return _engine

def get_engine():
    if _engine is None:
        raise RuntimeError("init_db() não foi chamado. Inicialize o banco antes de usar.")
    return _engine

@contextmanager
def get_session():
    """
    Context manager para sessões transacionais.
    Uso:
        with get_db_session() as session:
            session.add(objeto)
        #commit automático ao sair do bloco, 
        # rollback em caso de exceção.
    """

    if _SessionLocal is None:
        raise RuntimeError("init_db() não foi chamado.")
    
    session= _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Erro na sessão do banco de dados: %s", exc)
        raise
    finally:
        session.close()

@contextmanager
def get_read_session():
    """
    Sessão somente leitura, sem commit, sem rollback.
    Usada pelo dashboard T-22 e consultas que não escrevem no banco.
    """
    if _SessionLocal is None:
        raise RuntimeError("init_db() não foi chamado.")
    
    session= _SessionLocal()
    try:
        yield session
    finally:
        session.close()