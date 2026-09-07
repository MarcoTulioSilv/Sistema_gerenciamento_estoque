"""
gui.componentes.troca_modo.py
Overlay de transição animada entre os subsistemas Estoque e Patrimônio.

Metáfora espacial: Patrimônio mora à esquerda da tela, Estoque à direita.
Indo a Patrimônio, o véu entra pela esquerda e RECUA pela esquerda (vai e
volta). Voltando a Estoque, o véu entra pela direita e ATRAVESSA para a
esquerda — sai sempre pela esquerda, nos dois sentidos.
"""
import customtkinter as ctk

from gui.componentes.tema import COR_AZUL, COR_PETROLEO

_PASSO_MS = 16
_DURACAO_ENTRADA_MS = 170
_DURACAO_SAIDA_MS = 170


class TrocaModoOverlay(ctk.CTkFrame):
    """Véu deslizante que cobre a janela inteira durante a troca de subsistema."""

    def __init__(self, master):
        super().__init__(master, corner_radius=0)
        self._label_titulo = ctk.CTkLabel(self, text="", text_color="white",
                                          font=ctk.CTkFont(size=18, weight="bold"))
        self._label_sub = ctk.CTkLabel(self, text="Centro de Uro-Nefrologia", text_color="white",
                                       font=ctk.CTkFont(size=11))
        self._label_titulo.place(relx=0.5, rely=0.46, anchor="center")
        self._label_sub.place(relx=0.5, rely=0.54, anchor="center")

    def animar(self, indo_patrimonio: bool, callback_meio):
        """
        Toca a animação completa (entra, troca por baixo no meio, sai).

        callback_meio é chamado exatamente quando o véu cobre a tela
        inteira — é o momento de reconstruir sidebar/titlebar/conteúdo por
        baixo, sem que o usuário veja o "pulo".
        """
        cor = COR_PETROLEO if indo_patrimonio else COR_AZUL
        titulo = "Patrimônio" if indo_patrimonio else "Controle de Estoque"
        self.configure(fg_color=cor)
        self._label_titulo.configure(text=titulo)

        relx_inicial = -1.0 if indo_patrimonio else 1.0
        self.place(relx=relx_inicial, rely=0, relwidth=1, relheight=1)
        self.lift()

        self._deslizar(relx_inicial, 0.0, _DURACAO_ENTRADA_MS,
                       lambda: self._no_meio(callback_meio))

    def _no_meio(self, callback_meio):
        callback_meio()
        # Sai sempre pela esquerda, nos dois sentidos.
        self._deslizar(0.0, -1.0, _DURACAO_SAIDA_MS, self._remover)

    def _deslizar(self, relx_de: float, relx_para: float, duracao_ms: int, ao_terminar):
        passos = max(1, duracao_ms // _PASSO_MS)
        delta = (relx_para - relx_de) / passos

        def passo(i, relx_atual):
            if i >= passos:
                self.place(relx=relx_para, rely=0, relwidth=1, relheight=1)
                ao_terminar()
                return
            self.place(relx=relx_atual, rely=0, relwidth=1, relheight=1)
            self.after(_PASSO_MS, lambda: passo(i + 1, relx_atual + delta))

        passo(0, relx_de)

    def _remover(self):
        self.place_forget()
