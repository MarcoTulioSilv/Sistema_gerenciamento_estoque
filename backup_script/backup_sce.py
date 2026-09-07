"""
backup_script · backup_sce.py
Backup automático diário do banco de dados do SCE — Opção B do RNF-04
(mitiga o risco R-01 do DAS: o backup manual da tela T-18 só roda com o
SCE aberto).

Este script é standalone (não importa nada do pacote principal do SCE) e
deve ser executado no SERVIDOR (mesma máquina do MySQL), agendado no
Agendador de Tarefas do Windows via instalar_tarefa.bat.

Fluxo:
  1. Executa mysqldump e grava um arquivo .sql com timestamp.
  2. Registra o resultado (sucesso ou falha) na tabela job_log do próprio
     banco — a mesma tabela usada pelo backup manual — para que a tela
     T-18 do SCE possa exibir o histórico a partir de qualquer estação.
  3. Remove backups mais antigos que RETENCAO_DIAS.

Configuração: copie "backup.env.example" para "backup.env" nesta mesma
pasta e preencha os valores. Instale as dependências com:
    pip install -r requirements.txt
"""
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pymysql
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent
_CONFIG = {**dotenv_values(BASE_DIR / "backup.env"), **os.environ}

DB_HOST     = _CONFIG.get("DB_HOST", "127.0.0.1")
DB_PORT     = int(_CONFIG.get("DB_PORT", "3306"))
DB_NAME     = _CONFIG.get("DB_NAME", "sce_db")
DB_USER     = _CONFIG.get("DB_USER", "sce_backup")
DB_PASSWORD = _CONFIG.get("DB_PASSWORD", "")

BACKUP_DIR       = Path(_CONFIG.get("BACKUP_DIR", str(BASE_DIR / "Backups_SCE")))
RETENCAO_DIAS    = int(_CONFIG.get("RETENCAO_DIAS", "30"))
TIMEOUT_SEGUNDOS = int(_CONFIG.get("TIMEOUT_SEGUNDOS", "600"))

# Caminho do mysqldump. Por padrão usa "mysqldump" (depende do PATH), mas
# a tarefa agendada roda como SYSTEM, que tem um PATH próprio e pode não
# enxergar o mysqldump mesmo que ele funcione no seu usuário interativo
# (mesma causa que já pegou o python.exe neste servidor — ver
# instalar_tarefa.bat). Se acontecer de novo, defina o caminho completo em
# MYSQLDUMP_EXE no backup.env, ex.:
#   MYSQLDUMP_EXE=C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe
MYSQLDUMP_EXE = _CONFIG.get("MYSQLDUMP_EXE", "mysqldump")

JOB_NOME = "backup_automatico_servidor"

logger = logging.getLogger("backup_sce")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(
    BASE_DIR / "backup_sce.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler(sys.stdout))


def main() -> None:
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo = BACKUP_DIR / f"sce_db_{ts}.sql"
    sucesso = False
    detalhe = ""

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        _executar_mysqldump(arquivo)
        tamanho_kb = arquivo.stat().st_size // 1024
        detalhe = f"Backup concluído: {arquivo.name} ({tamanho_kb} KB)"
        sucesso = True
        logger.info(detalhe)

    except subprocess.CalledProcessError as exc:
        stderr  = (exc.stderr or b"").decode(errors="replace").strip()
        detalhe = f"mysqldump falhou: {stderr[:300]}"
        logger.error(detalhe)

    except FileNotFoundError:
        detalhe = "Comando 'mysqldump' não encontrado no PATH do servidor."
        logger.error(detalhe)

    except subprocess.TimeoutExpired:
        detalhe = f"Timeout: o backup excedeu {TIMEOUT_SEGUNDOS}s."
        logger.error(detalhe)

    except Exception as exc:
        detalhe = f"Erro inesperado no backup: {exc}"
        logger.error(detalhe)

    if not sucesso:
        _remover_arquivo_parcial(arquivo)

    _registrar_job_log(sucesso, detalhe)

    if sucesso:
        _limpar_backups_antigos()


def _remover_arquivo_parcial(arquivo: Path) -> None:
    """Remove o .sql vazio/incompleto deixado pelo open() quando o mysqldump falha."""
    try:
        if arquivo.exists():
            arquivo.unlink()
    except OSError as exc:
        logger.warning("Não foi possível remover arquivo parcial %s: %s", arquivo.name, exc)


def _executar_mysqldump(arquivo: Path) -> None:
    cmd = [
        MYSQLDUMP_EXE,
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        f"--password={DB_PASSWORD}",
        "--single-transaction",   # consistência InnoDB sem lock
        "--routines",
        "--triggers",
        "--set-gtid-purged=OFF",  # compatibilidade com servidores sem GTID
        DB_NAME,
    ]
    with open(arquivo, "w", encoding="utf-8") as f_out:
        subprocess.run(
            cmd,
            stdout  = f_out,
            stderr  = subprocess.PIPE,
            timeout = TIMEOUT_SEGUNDOS,
            check   = True,
        )


def _registrar_job_log(sucesso: bool, detalhe: str) -> None:
    """Grava o resultado em job_log via pymysql puro (mesma tabela do backup manual da T-18)."""
    try:
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, connect_timeout=10,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO job_log (job_nome, executado_em, sucesso, detalhe) "
                    "VALUES (%s, %s, %s, %s)",
                    (JOB_NOME, datetime.now(timezone.utc).replace(tzinfo=None), sucesso, detalhe[:255]),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Erro ao registrar job_log do backup: %s", exc)


def _limpar_backups_antigos() -> None:
    """Remove backups com mais de RETENCAO_DIAS dias. RETENCAO_DIAS <= 0 desativa a limpeza."""
    if RETENCAO_DIAS <= 0:
        return
    limite = datetime.now() - timedelta(days=RETENCAO_DIAS)
    for arquivo in BACKUP_DIR.glob("sce_db_*.sql"):
        try:
            if datetime.fromtimestamp(arquivo.stat().st_mtime) < limite:
                arquivo.unlink()
                logger.info("Backup antigo removido: %s", arquivo.name)
        except OSError as exc:
            logger.warning("Não foi possível remover %s: %s", arquivo.name, exc)


if __name__ == "__main__":
    main()
