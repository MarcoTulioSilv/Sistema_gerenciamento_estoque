"""
Modulo_02_estoque · danfe_entry_assistant.py
DanfeEntryAssistant — RF-04b / AD-12 / ERS v1.6

Fluxo de entrada via chave de acesso DANFE:
  1. Técnico lê o código de barras do DANFE com o leitor USB.
  2. DanfeEntryAssistant valida a chave (44 dígitos + dígito verificador MOD11).
  3. Extrai o número da NF da chave (posições 26–34, sem zeros à esquerda).
  4. Monta a URL do portal SEFAZ e abre no navegador padrão do Windows.
  5. Técnico resolve o CAPTCHA externamente e preenche os dados do lote no SCE.

Decisão arquitetural AD-12:
  O SCE NÃO automatiza nem realiza scraping do portal SEFAZ.
  O único acesso externo é webbrowser.open() — sem HTTP client, sem sessão.
"""
import logging
import webbrowser

logger= logging.getLogger(__name__)


class DanfeEntryAssistant:
    """
    Utilitário leve para o fluxo de entrada via chave de acesso DANFE.
    sem estado- todos os metodos são estaticos
    """
    @staticmethod
    def validar_chave(chave: str)-> tuple[bool, str]:
        """
        Valida a chave de acesso NF-e de 44 dígitos.

        Verifica:
          - Comprimento exato de 44 caracteres numéricos
          - Dígito verificador (posição 44) calculado por MOD11

        Returns:
            (True, "")          — chave válida
            (False, mensagem)   — chave inválida com descrição do erro
        """
        chave = chave.strip().replace(" ", "")

        if not chave.isdigit():
            return False, "A chave de acesso deve conter apenas dígitos numéricos."

        if len(chave) != 44:
            return False, (
                f"Chave de acesso inválida: {len(chave)} dígitos lidos "
                f"(esperado: 44)."
            )

        # Validação MOD11 com pesos 2..9 ciclando da direita para a esquerda
        digitos = [int(d) for d in chave]
        soma = 0
        peso = 2
        for d in reversed(digitos[:-1]):  # ignora o último (dígito verificador)
            soma += d * peso
            peso = 2 if peso == 9 else peso + 1

        resto = soma % 11
        dv_esperado = 0 if resto < 2 else 11 - resto
        dv_lido = digitos[-1]

        if dv_lido != dv_esperado:
            return False, (
                f"Dígito verificador inválido: lido={dv_lido}, "
                f"esperado={dv_esperado}. Verifique se o leitor leu todos os 44 dígitos."
            )

        return True, ""
    
    @staticmethod
    def extrair_numero_nf(chave:str)->str:
        chave = chave.strip()
        if len(chave) != 44:
            return ""
        numero_raw = chave[25:34]
        return str(int(numero_raw)) 
    
    @staticmethod
    def extrair_serie(chave: str)-> str:
        chave = chave.strip()
        if len(chave)!=44:
            return""
        return str(int(chave[22:25]))

    
    @staticmethod
    def processar_chave(chave:str)-> dict:
        chave = chave.strip()
        valida, erro = DanfeEntryAssistant.validar_chave(chave)
        if not valida:
            return {"valida": False, "erro": erro,
                    "numero_nf": "", "serie": "", "chave": chave}

        return {
            "valida":         True,
            "erro":           "",
            "numero_nf":      DanfeEntryAssistant.extrair_numero_nf(chave),
            "serie":          DanfeEntryAssistant.extrair_serie(chave),
            "chave":          chave,
        }