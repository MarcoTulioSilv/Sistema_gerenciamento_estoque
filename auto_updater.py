# =============================================================
# SCE — Sistema de Controle de Estoque · Uronefrologia
# auto_updater.py  —  MOD-00 / utilitário de atualização
#
# Responsabilidade:
#   Verificar, no início de cada sessão, se existe versão mais
#   recente disponível no share de rede e aplicá-la de forma
#   silenciosa mediante confirmação do usuário.
#
# Dependências: apenas stdlib + packaging (já inclusa no venv)
# =============================================================

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Configuração — ajuste conforme o ambiente da clínica
# ------------------------------------------------------------------

# Versão atual do executável.
# Manter sincronizado com #define AppVersion no SCE_Setup.iss
# e com o campo "version" em version.json gerado pelo build.bat.
LOCAL_VERSION = "1.0.4"

# Caminho UNC do share no servidor MySQL.
# Formato: \\IP_SERVIDOR\NOME_DO_SHARE
# Requer que a conta Windows das estações tenha leitura no share.
UPDATE_SHARE = r"\\192.168.0.150\SCE_Updates"

# Nome fixo do manifesto de versão dentro do share.
VERSION_FILE = "version.json"

# Timeout (segundos) para acesso ao share.
# Evita travar a inicialização se o servidor estiver offline.
NETWORK_TIMEOUT = 3


# ------------------------------------------------------------------
# Estrutura de resultado
# ------------------------------------------------------------------

class UpdateInfo:
    """Informações retornadas quando uma atualização está disponível."""

    def __init__(self, version: str, filename: str):
        self.version = version
        self.filename = filename

    def __repr__(self) -> str:
        return f"UpdateInfo(version={self.version!r}, file={self.filename!r})"


# ------------------------------------------------------------------
# Funções públicas
# ------------------------------------------------------------------

def verificar_atualizacao() -> Optional[UpdateInfo]:
    """
    Tenta ler version.json do share e compara com LOCAL_VERSION.

    Retorna UpdateInfo se houver versão mais nova, None caso contrário.
    Engole silenciosamente qualquer erro de rede ou I/O — o sistema
    deve iniciar normalmente mesmo sem conectividade ao share.
    """
    version_path = Path(UPDATE_SHARE) / VERSION_FILE
    try:
        # Path.read_text tenta abrir o arquivo; se o share estiver
        # inacessível, levanta OSError/TimeoutError que capturamos abaixo.
        raw = version_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        remote_version: str = data["version"]
        filename: str = data["file"]

        if _versao_maior(remote_version, LOCAL_VERSION):
            logger.info(
                "Atualização disponível: %s → %s (%s)",
                LOCAL_VERSION,
                remote_version,
                filename,
            )
            return UpdateInfo(version=remote_version, filename=filename)

        logger.debug(
            "Sistema atualizado (local=%s, remoto=%s)",
            LOCAL_VERSION,
            remote_version,
        )
        return None

    except FileNotFoundError:
        logger.debug("version.json não encontrado em %s", UPDATE_SHARE)
        return None
    except (OSError, TimeoutError) as exc:
        # Share offline ou sem permissão — ignora silenciosamente
        logger.debug("Share inacessível (%s): %s", UPDATE_SHARE, exc)
        return None
    except (json.JSONDecodeError, KeyError) as exc:
        # version.json malformado — avisa no log mas não trava
        logger.warning("version.json inválido: %s", exc)
        return None
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Erro inesperado ao verificar atualização: %s", exc)
        return None


def aplicar_atualizacao(info: UpdateInfo) -> None:
    """
    Copia o instalador do share para %TEMP% e o executa em modo
    silencioso (/SILENT /CLOSEAPPLICATIONS).

    O Inno Setup fecha o SCE.exe em execução antes de reinstalar,
    por isso encerramos o processo atual logo após o Popen.

    Em caso de falha na cópia, loga o erro e retorna sem encerrar
    o SCE — o usuário continua usando a versão atual.
    """
    src = Path(UPDATE_SHARE) / info.filename
    dst = Path(tempfile.gettempdir()) / info.filename

    try:
        logger.info("Copiando %s → %s", src, dst)
        shutil.copy2(src, dst)
    except OSError as exc:
        logger.error("Falha ao copiar instalador: %s", exc)
        return

    try:
        # /SILENT     — sem wizard, sem perguntas
        # /CLOSEAPPLICATIONS — fecha SCE_Uro_v1.exe se estiver aberto
        # /NORESTART  — não reinicia o Windows
        subprocess.Popen(
            [str(dst), "/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"],
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        logger.info("Instalador iniciado. Encerrando SCE.")
        sys.exit(0)
    except OSError as exc:
        logger.error("Falha ao executar instalador: %s", exc)


# ------------------------------------------------------------------
# Comparação de versão semântica
# ------------------------------------------------------------------

def _versao_maior(remota: str, local: str) -> bool:
    """
    Retorna True se `remota` for semanticamente maior que `local`.
    Usa packaging.version quando disponível; recai em comparação
    tupla de inteiros como fallback (evita ImportError no bundle).
    """
    try:
        from packaging.version import Version  # type: ignore
        return Version(remota) > Version(local)
    except ImportError:
        pass

    # Fallback: converte "1.2.3" em (1, 2, 3) e compara
    def _parse(v: str):
        try:
            return tuple(int(x) for x in v.strip().split("."))
        except ValueError:
            return (0,)

    return _parse(remota) > _parse(local)
