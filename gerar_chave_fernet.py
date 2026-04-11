"""
scripts/gerar_chave_fernet.py
Gera a chave de criptografia Fernet para o arquivo .env.
Execute UMA VEZ durante a configuração inicial.
A chave gerada deve ser colocada em FERNET_KEY no .env.
ATENÇÃO: se a chave for perdida, os dados criptografados (App Password Gmail)
         não poderão ser recuperados e precisarão ser reconfigurados.
"""
from cryptography.fernet import Fernet

chave = Fernet.generate_key().decode()
print("Chave Fernet gerada:\n")
print(f"FERNET_KEY={chave}\n")
print("Cole esta linha no arquivo .env do projeto.")
print("GUARDE esta chave em local seguro — não pode ser recuperada se perdida.")
