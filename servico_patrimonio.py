"""
SCE — Sistema de Controle de Estoque do Centro de Uronefrologia
servico_patrimonio.py — ponto de entrada do ColetaWebService (MOD-07, AD-14)

Processo headless, sem GUI, sem scheduler, sem verificação de atualização —
roda em execução permanente no servidor MySQL (DAS v1.5 §7.1/§7.3/§7.4),
independente de qualquer estação desktop estar aberta. Compartilha o mesmo
código/serviços do SCE (Modulo_06_dados, Modulo_07_patrimonio), só que num
processo à parte do app desktop (main.py).

Implantação: script rodando via python.exe da venv do servidor + Tarefa
Agendada do Windows (ver instalar_tarefa_coleta.bat) — não é empacotado como
.exe separado (mesmo padrão de backup_script/backup_sce.py).
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# Garante que o diretório raiz esteja no path quando executado diretamente
sys.path.insert(0, str(Path(__file__).parent))

from Modulo_06_dados import init_db
from Modulo_05_admin import ConfigService

# ---------------------------- Logging ---------------------------------------
# Arquivo PRÓPRIO, separado de sce.log — este processo roda 24/7 sem
# reinício por sessão de usuário, então precisa de rotação (main.py não
# precisa: reinicia a cada login do técnico).

local_app_data = os.getenv("LOCALAPPDATA")
if not local_app_data:
    local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")

pasta_log = os.path.join(local_app_data, "SCE_Urofrologia")
arquivo_log = os.path.join(pasta_log, "coleta_web_service.log")

try:
    os.makedirs(pasta_log, exist_ok=True)
except Exception as e:
    print(f"ERRO AO CRIAR PASTA DE LOG: {e}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            arquivo_log, encoding="utf-8", maxBytes=5 * 1024 * 1024, backupCount=5
        ),
    ],
    force=True,
)

logger = logging.getLogger("sce.servico_patrimonio")

_PORTA_PADRAO = 8080


def main():
    logger.info("Iniciando ColetaWebService (MOD-07)")

    try:
        init_db()
        logger.info("Banco de dados inicializado com sucesso")
    except ConnectionError as exc:
        logger.critical("Não foi possível conectar ao banco de dados MySQL: %s", exc)
        sys.exit(1)

    from Modulo_07_patrimonio.coleta_web_service import criar_app
    app = criar_app()

    porta_cfg = ConfigService.get("coleta_porta")
    try:
        porta = int(porta_cfg) if porta_cfg else _PORTA_PADRAO
    except ValueError:
        logger.error(
            "coleta_porta='%s' não é um número válido — usando porta padrão %s. "
            "Corrija em configuracao.coleta_porta.",
            porta_cfg, _PORTA_PADRAO,
        )
        porta = _PORTA_PADRAO

    logger.info("ColetaWebService ouvindo em 0.0.0.0:%s", porta)

    from waitress import serve
    serve(app, host="0.0.0.0", port=porta)

    logger.info("ColetaWebService encerrado")


if __name__ == "__main__":
    main()
