"""
SCE- Sistema de Controle de Estoque do Centro de Uronefrologia
main.py- ponto de entrada da aplicação
sprint 0- inicializa o banco, controi janela prinicipal e inicia o loop da GUI
"""

import sys
import logging
from pathlib import Path
from venv import logger

#Garante que o diretório raiz esteja no path quando executado via pyInstaller
sys.path.insert(0, str(Path(__file__).parent))

from modulo_06_dados import init_db
from gui.app import SCEApp

#---------------------------Logging---------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sce.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("sce.main")


def main():
    logger.info("Iniciando SCE V1.0.0")

    #1. Inicializar banco de dados
    try:
        init_db()
        logger.info("Banco de dados inicializado com sucesso")
    except ConnectionError as exc:
        #exibe mensagem de erro em tkinter simples antes da gui completa
        import tkinter as tk
        from tkinter import messagebox
        root= tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Erro de Conexão",
            f"Não foi possível conectar ao banco de dados MySQL.\n\n{exc}\n\n"
            "Verifique o arquivo .env e se o servidor MySQL está rodando."
        )
        root.destroy()
        sys.exit(1)

    #iniciar GUI
    app= SCEApp()
    app.mainloop()
    logger.info("SCE encerrado")


if __name__ == "__main__":
    main()    