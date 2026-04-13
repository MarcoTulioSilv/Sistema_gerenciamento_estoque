"""
scripts/testar_sintaxe.py
Valida a sintaxe de todos os arquivos .py do projeto sem precisar
instalar as dependências (útil no ambiente de CI e no sandbox).
"""
import ast
import sys
from pathlib import Path


def testar_arquivo(caminho: Path) -> tuple[bool, str]:
    try:
        fonte = caminho.read_text(encoding="utf-8")
        ast.parse(fonte)
        return True, ""
    except SyntaxError as e:
        return False, f"Linha {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)


def main():
    raiz = Path(__file__).parent.parent
    arquivos = sorted(raiz.rglob("*.py"))
    
    erros = []
    ok = 0
    
    for arq in arquivos:
        relativo = arq.relative_to(raiz)
        valido, msg = testar_arquivo(arq)
        if valido:
            print(f"  OK   {relativo}")
            ok += 1
        else:
            print(f"  ERRO {relativo} → {msg}")
            erros.append((relativo, msg))
    
    print(f"\n{'─'*50}")
    print(f"Resultado: {ok} OK  |  {len(erros)} ERRO(S)")
    
    if erros:
        print("\nArquivos com erro:")
        for arq, msg in erros:
            print(f"  {arq}: {msg}")
        sys.exit(1)
    else:
        print("Todos os arquivos com sintaxe válida.")
        sys.exit(0)


if __name__ == "__main__":
    main()
