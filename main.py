"""
SCE- Sistema de Controle de Estoque do Centro de Uronefrologia
main.py- ponto de entrada da aplicação
sprint 0- inicializa o banco, controi janela prinicipal e inicia o loop da GUI
"""

import sys
import logging
from pathlib import Path

#Garante que o diretório raiz esteja no path quando executado via pyInstaller
sys.path.insert(0, str(Path(__file__).parent))

from Modulo_06_dados import init_db
from gui.app import SCEApp
from auto_updater import verificar_atualizacao, aplicar_atualizacao
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

def _checar_e_perguntar() -> None:
    """
    Verifica o share de atualização e exibe um dialog nativo do
    Windows (tkinter.messagebox) para não depender do CTk ainda
    não inicializado.
 
    Se o usuário confirmar, baixa e executa o instalador e encerra.
    Se recusar ou em caso de erro, continua a inicialização normal.
    """
    import tkinter as tk
    import tkinter.messagebox as mb
 
    info = verificar_atualizacao()
    if info is None:
        return  # sem atualização ou share offline — segue em frente
 
    # Root oculto só para hospedar o messagebox
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
 
    resposta = mb.askyesno(
        title="Atualização disponível",
        message=(
            f"Nova versão disponível: {info.version}\n\n"
            "Deseja atualizar agora?\n\n"
            "O sistema será fechado e reinstalado automaticamente.\n"
            "Você poderá usá-lo novamente em instantes."
        ),
        icon=mb.INFO,
        default=mb.YES,
    )
    root.destroy()
 
    if resposta:
        aplicar_atualizacao(info)
        # Se aplicar_atualizacao retornar (falha na cópia),
        # continua a inicialização normal abaixo.
 
 


def main():
    logger.info("Iniciando SCE V1.0.0")
    _checar_e_perguntar()

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
    app.pararScheduler()
    logger.info("SCE encerrado")


if __name__ == "__main__":
    main()    