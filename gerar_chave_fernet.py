"""
scripts/gerar_chave_fernet.py
Gera a chave Fernet (AES-128) usada para criptografar o App Password Gmail (AD-10).

Deve ser executado UMA ÚNICA VEZ antes da primeira implantação.
A chave gerada é adicionada ao arquivo .env do projeto.

Uso:
    python scripts/gerar_chave_fernet.py

ATENÇÃO:
  - Não perca esta chave. Sem ela, o App Password criptografado não pode
    ser recuperado e precisará ser reconfigurado via T-17.
  - Não versione o .env no git (já deve estar no .gitignore).
  - Em caso de troca de chave, reconfigure o Gmail via T-17 (T-17 re-criptografa).
"""
import sys
from pathlib import Path

from cryptography.fernet import Fernet

RAIZ    = Path(__file__).resolve().parent.parent
ENV     = RAIZ / ".env"
CHAVE   = "FERNET_KEY"


def main():
    print(f"\n{'='*60}")
    print("  SCE — Gerador de chave Fernet")
    print(f"{'='*60}\n")

    # Verificar se já existe
    if ENV.exists():
        conteudo = ENV.read_text(encoding="utf-8")
        if CHAVE in conteudo:
            print(f"  AVISO: '{CHAVE}' já existe em {ENV}.")
            resp = input("  Deseja sobrescrever? [s/N] ").strip().lower()
            if resp != "s":
                print("  Operação cancelada.\n")
                sys.exit(0)

    # Gerar nova chave
    chave = Fernet.generate_key().decode("utf-8")

    # Adicionar / substituir no .env
    if ENV.exists():
        linhas = ENV.read_text(encoding="utf-8").splitlines()
        linhas = [l for l in linhas if not l.startswith(f"{CHAVE}=")]
        linhas.append(f"{CHAVE}={chave}")
        ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        print(f"  Chave atualizada em: {ENV}")
    else:
        ENV.write_text(f"{CHAVE}={chave}\n", encoding="utf-8")
        print(f"  Arquivo .env criado em: {ENV}")

    print(f"\n  Chave: {chave}")
    print(f"\n  Próximos passos:")
    print(f"    1. Configure o Gmail via Administração → Config. Gmail (T-17).")
    print(f"    2. Nunca delete esta chave — sem ela os e-mails param de funcionar.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
