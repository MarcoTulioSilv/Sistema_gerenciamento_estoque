"""
scripts/preview_tela.py

Harness de preview isolado para telas do MOD-07 (customtkinter) — abre uma
tela sozinha, sem login e sem o roteamento completo de gui/app.py. F5
recarrega o módulo da tela do zero via importlib.reload: edita o arquivo da
tela, salva, aperta F5 na janela — sem reiniciar o processo Python, sem
logar de novo.

Não é hot reload de verdade (Tkinter não suporta re-render incremental de
widget já construído) — é reconstrução completa da tela a partir do módulo
recarregado, o que ainda assim é bem mais rápido que reabrir o app inteiro.

Uso:
    python scripts/preview_tela.py bens_patrimoniais
    python scripts/preview_tela.py movimentar_bem --extra 3
    python scripts/preview_tela.py novo_bem --usuario-id 3
    python scripts/preview_tela.py --listar

Dentro da janela: F5 recarrega a tela atual. Botões que chamam
on_navigate("algum_destino") funcionam normalmente se o destino também
estiver no registro _TELAS abaixo (ex.: T-23 -> "Abrir" -> T-25); destinos
fora do registro só geram um log, sem travar a janela.
"""
import argparse
import importlib
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import customtkinter as ctk

from Modulo_06_dados import init_db, PerfilEnum
from Modulo_05_admin import UsuarioService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("preview_tela")

# destino -> (módulo, classe, nome do kwarg de extra ou None)
_TELAS = {
    "retirada":          ("gui.telas.t09_retirada",          "TelaRetirada",         "produto_id"),
    "transferencia":     ("gui.telas.t09b_transferencia",    "TelaTransferencia",    "produto_id"),
    "bens_patrimoniais": ("gui.telas.t23_bens_patrimoniais", "TelaBensPatrimoniais", None),
    "novo_bem":          ("gui.telas.t24_cadastro_bem",      "TelaCadastroBem",      "bem_id"),
    "editar_bem":        ("gui.telas.t24_cadastro_bem",      "TelaCadastroBem",      "bem_id"),
    "movimentar_bem":    ("gui.telas.t25_movimentacao_baixa", "TelaMovimentacaoBaixa", "bem_id"),
    "localizacoes":      ("gui.telas.t28_localizacoes",      "TelaLocalizacoes",     None),
    "inventario":        ("gui.telas.t26_inventario",        "TelaInventario",       None),
    "transferencias":     ("gui.telas.t09b_transferencia",    "TelaTransferencia",   None),
}


class Harness(ctk.CTk):
    def __init__(self, destino: str, usuario, extra=None):
        super().__init__()
        self._usuario = usuario
        self._destino = destino
        self._extra = 4
        self._tela_atual = None

        self.geometry("1100x650")

        barra = ctk.CTkFrame(self, height=28, fg_color="#1F5F5B")
        barra.pack(fill="x")
        barra.pack_propagate(False)
        self._lbl_status = ctk.CTkLabel(barra, text="", text_color="white", font=ctk.CTkFont(size=11))
        self._lbl_status.pack(side="left", padx=10)

        self._area = ctk.CTkFrame(self, fg_color="transparent")
        self._area.pack(fill="both", expand=True)

        self.bind_all("<F5>", lambda e: self.recarregar())
        self._montar(destino, extra)

    def _on_navigate(self, destino: str, extra=None):
        logger.info("on_navigate(%r, extra=%r)", destino, extra)
        if destino not in _TELAS:
            logger.warning("Destino '%s' não está no registro do harness — ignorado "
                            "(edite _TELAS em scripts/preview_tela.py se quiser navegar até lá).", destino)
            return
        self._montar(destino, extra)

    def recarregar(self):
        logger.info("Recarregando '%s'...", self._destino)
        self._montar(self._destino, self._extra, forcar_reload=True)

    def _montar(self, destino: str, extra=None, forcar_reload: bool = False):
        if destino not in _TELAS:
            logger.error("Tela '%s' não registrada. Opções: %s", destino, ", ".join(sorted(_TELAS)))
            return

        modulo_nome, classe_nome, kwarg_extra = _TELAS[destino]

        if self._tela_atual is not None:
            if hasattr(self._tela_atual, "limpar_memoria"):
                try:
                    self._tela_atual.limpar_memoria()
                except Exception:
                    logger.exception("Erro em limpar_memoria() da tela anterior")
            self._tela_atual.destroy()
            self._tela_atual = None

        modulo = sys.modules.get(modulo_nome)
        try:
            if modulo is None:
                modulo = importlib.import_module(modulo_nome)
            elif forcar_reload:
                modulo = importlib.reload(modulo)
        except Exception:
            logger.exception("Erro ao (re)importar '%s' — corrija o arquivo e aperte F5 de novo.", modulo_nome)
            return

        classe = getattr(modulo, classe_nome)
        kwargs = {"usuario": self._usuario, "on_navigate": self._on_navigate}
        if kwarg_extra:
            kwargs[kwarg_extra] = extra

        try:
            tela = classe(self._area, **kwargs)
        except Exception:
            logger.exception("Erro ao construir a tela '%s' — corrija e aperte F5 de novo.", destino)
            return

        tela.pack(fill="both", expand=True)
        self._tela_atual = tela
        self._destino = destino
        self._extra = extra
        self._lbl_status.configure(
            text=f"{destino}  ·  usuário: {self._usuario.nome} [{self._usuario.perfil.value}]  ·  F5 recarrega")
        logger.info("Tela '%s' montada.", destino)


def _usuario_padrao():
    """Primeiro usuário TI ativo — passa em qualquer checagem de permissão do MOD-07."""
    for u in UsuarioService.listar():
        if u.perfil == PerfilEnum.ti and u.ativo:
            return u
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Preview isolado de uma tela do MOD-07, com F5 para recarregar.")
    parser.add_argument("destino", nargs="?", choices=sorted(_TELAS), help="Tela a abrir")
    parser.add_argument("--usuario-id", type=int, default=None,
                        help="Id do usuário a simular (padrão: primeiro TI ativo)")
    parser.add_argument("--extra", default=None,
                        help="Valor extra (ex: bem_id) para telas que exigem")
    parser.add_argument("--listar", action="store_true", help="Lista as telas registradas e sai")
    args = parser.parse_args()

    if args.listar or not args.destino:
        print("Telas disponíveis:")
        for nome in sorted(_TELAS):
            print(f"  {nome}")
        sys.exit(0)

    init_db()

    if args.usuario_id:
        usuario = UsuarioService.buscar(args.usuario_id)
        if not usuario:
            print(f"Usuário {args.usuario_id} não encontrado.")
            sys.exit(1)
    else:
        usuario = _usuario_padrao()
        if not usuario:
            print("Nenhum usuário TI ativo encontrado — informe --usuario-id explicitamente.")
            sys.exit(1)

    extra = int(args.extra) if args.extra and args.extra.isdigit() else args.extra

    app = Harness(args.destino, usuario, extra)
    app.mainloop()


if __name__ == "__main__":
    main()
