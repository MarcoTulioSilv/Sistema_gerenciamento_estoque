import json
import os
import time
import webbrowser
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class DadosSefaz:
    sucesso: bool = False
    erro: str = ""
    numero_nf: str = ""
    data_emissao: date | None = None
    nome_emitente: str = ""
    itens: list = field(default_factory=list)

def iniciar_escuta_e_abrir_navegador(chave: str) -> DadosSefaz:
    """Vigia a pasta de Downloads aguardando o JSON da extensão."""
    
    # Caminho da pasta de Downloads do Windows
    pasta_downloads = Path(os.path.expanduser("~")) / "Downloads"
    tempo_limite = 300 # 5 minutos
    inicio = time.time()

    # Abre o portal SEFAZ
    url = f"https://www.nfe.fazenda.gov.br/portal/consultaResumo.aspx?tipoConteudo=7PhJ+gAVw2g=&chave={chave}"
    webbrowser.open(url)

    logger.info(f"Vigiando pasta: {pasta_downloads}")

    while time.time() - inicio < tempo_limite:
        # Busca arquivos sce_nf_*.json
        for arquivo in pasta_downloads.glob("sce_nf_*.json"):
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    dados_json = json.load(f)
                
                # Verifica se é um arquivo legítimo do nosso sistema
                if dados_json.get("identificador_sce") == "NF_ENTRADA":
                    logger.info(f"Arquivo detectado e lido: {arquivo.name}")
                    
                    dt_emissao = None
                    if dados_json.get("data_emissao"):
                        try:
                            dt_emissao = datetime.strptime(dados_json["data_emissao"], "%d/%m/%Y").date()
                        except ValueError: pass

                    # Remove o arquivo após a leitura para não duplicar
                   # os.remove(arquivo)

                    return DadosSefaz(
                        sucesso=True,
                        numero_nf=dados_json.get("numero_nf", ""),
                        nome_emitente=dados_json.get("nome_emitente", ""),
                        data_emissao=dt_emissao,
                        itens=dados_json.get("itens", [])
                    )
            except Exception as e:
                logger.error(f"Erro ao ler arquivo de integração: {e}")
        
        time.sleep(1.5) # Intervalo entre checagens

    return DadosSefaz(sucesso=False, erro="Tempo esgotado aguardando o arquivo nos Downloads.")