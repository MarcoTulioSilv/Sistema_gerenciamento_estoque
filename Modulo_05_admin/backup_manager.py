"""
Modulo_05_admin · backup_manager.py
Sprint 6 — BackupManager: backup do banco de dados via mysqldump (UC-19, RNF-04).

Responsabilidades:
  - Executar mysqldump em thread separada (não bloqueia a GUI).
  - Nomear o arquivo com timestamp automático.
  - Registrar sucesso/falha em job_log para rastreabilidade do TI.
  - Ler credenciais do banco exclusivamente do .env (mesma fonte que o SQLAlchemy).

Uso pela tela T-18:
    manager = BackupManager()
    manager.executar(
        diretorio  = Path("C:/SCE/backups"),
        on_sucesso = lambda msg: banner.sucesso(msg),
        on_erro    = lambda msg: banner.erro(msg),
    )
"""
import logging
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values

from Modulo_06_dados import get_session, JobLog

logger = logging.getLogger(__name__)


def _ler_db_config() -> dict[str, str]:
    """
    Lê as credenciais de conexão do banco a partir do .env e das
    variáveis de ambiente do processo. Mesma ordem que o database.py usa.
    """
    env = dotenv_values(".env")
    return {
        "host":   env.get("DB_HOST",     os.getenv("DB_HOST",     "127.0.0.1")),
        "port":   env.get("DB_PORT",     os.getenv("DB_PORT",     "3306")),
        "user":   env.get("DB_USER",     os.getenv("DB_USER",     "root")),
        "passwd": env.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        "db":     env.get("DB_NAME",     os.getenv("DB_NAME",     "sce_db")),
    }


class BackupManager:
    """Gerencia backups do banco de dados via mysqldump."""

    # ── API pública ───────────────────────────────────────────────────────────

    def executar(
        self,
        diretorio:  Path,
        on_sucesso: callable,
        on_erro:    callable,
    ) -> None:
        """
        Inicia o backup em thread daemon para não bloquear a GUI.

        Args:
            diretorio:  Path do diretório de destino (criado se não existir).
            on_sucesso: callback(msg: str) chamado na thread principal ao terminar.
            on_erro:    callback(msg: str) chamado na thread principal em caso de erro.
        """
        try:
            diretorio.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            on_erro(f"Não foi possível criar o diretório de backup: {exc}")
            return

        threading.Thread(
            target  = self._rodar,
            args    = (diretorio, on_sucesso, on_erro),
            daemon  = True,
            name    = "BackupManager",
        ).start()

    # ── Execução interna ──────────────────────────────────────────────────────

    def _rodar(
        self,
        diretorio:  Path,
        on_sucesso: callable,
        on_erro:    callable,
    ) -> None:
        """Corpo do backup — roda em thread separada."""
        cfg      = _ler_db_config()
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo  = diretorio / f"sce_db_{ts}.sql"
        sucesso  = False
        detalhe  = ""

        try:
            cmd = [
                "mysqldump",
                f"--host={cfg['host']}",
                f"--port={cfg['port']}",
                f"--user={cfg['user']}",
                f"--password={cfg['passwd']}",
                "--single-transaction",   # consistência InnoDB sem lock
                "--routines",
                "--triggers",
                "--set-gtid-purged=OFF",  # compatibilidade com servidores sem GTID
                cfg["db"],
            ]

            with open(arquivo, "w", encoding="utf-8") as f_out:
                resultado = subprocess.run(
                    cmd,
                    stdout  = f_out,
                    stderr  = subprocess.PIPE,
                    timeout = 300,           # 5 min — suficiente para qualquer clínica
                    check   = True,
                )

            tamanho_kb = arquivo.stat().st_size // 1024
            msg     = f"Backup concluído: {arquivo.name} ({tamanho_kb} KB)"
            detalhe = msg
            sucesso = True
            logger.info("Backup OK: %s", arquivo)
            on_sucesso(msg)

        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip()
            msg    = f"mysqldump falhou: {stderr[:300]}"
            detalhe = msg
            logger.error("Backup falhou: %s", msg)
            on_erro(msg)

        except FileNotFoundError:
            msg = (
                "Comando 'mysqldump' não encontrado. "
                "Instale o MySQL Client e adicione ao PATH do sistema."
            )
            detalhe = msg
            logger.error(msg)
            on_erro(msg)

        except subprocess.TimeoutExpired:
            msg = "Timeout: o backup demorou mais de 5 minutos. Verifique o servidor MySQL."
            detalhe = msg
            logger.error(msg)
            on_erro(msg)

        except Exception as exc:
            msg     = f"Erro inesperado no backup: {exc}"
            detalhe = msg
            logger.error(msg)
            on_erro(msg)

        finally:
            self._registrar_job_log(sucesso=sucesso, detalhe=detalhe)

    # ── Job log ───────────────────────────────────────────────────────────────

    @staticmethod
    def _registrar_job_log(sucesso: bool, detalhe: str) -> None:
        """Registra a execução do backup em job_log para rastreabilidade (RNF-06)."""
        try:
            with get_session() as s:
                s.add(JobLog(
                    job_nome     = "backup_manual",
                    executado_em = datetime.utcnow(),
                    sucesso      = sucesso,
                    detalhe      = detalhe[:255],
                ))
        except Exception as exc:
            logger.error("Erro ao registrar job_log do backup: %s", exc)
