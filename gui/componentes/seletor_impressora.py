"""
gui.componentes.seletor_impressora.py
Painel flutuante de seleção de impressora (MOD-07, RF-28.2) — reutilizado
por T-23 e T-24 antes de "Imprimir na térmica" (impressão a cabo).
"""
import logging

import customtkinter as ctk

from gui.componentes.form_widgets import FeedbackBanner

logger = logging.getLogger(__name__)

from gui.componentes.tema import COR_PETROLEO, COR_PETROLEO_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO


class SeletorImpressora(ctk.CTkFrame):
    """
    Painel flutuante: lista as impressoras instaladas na estação e confirma
    a escolha. Recebe `servico` (PatrimonioService) já instanciado pelo
    chamador — não importa o serviço aqui, respeita a Regra 1 igual às
    telas que o usam.
    """

    def __init__(self, master, servico, usuario, on_confirmar, on_cancelar):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=10,
                         border_width=1, border_color=COR_CINZA_B)
        self._servico = servico
        self._usuario = usuario
        self._on_confirmar = on_confirmar
        self._on_cancelar = on_cancelar
        self._var_impressora = ctk.StringVar(value="")
        self._construir()
        self._carregar()

    def _construir(self):
        ctk.CTkLabel(self, text="Selecionar impressora", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COR_PETROLEO).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Impressão a cabo — escolha a impressora conectada a esta estação.",
                     text_color="#888780", font=ctk.CTkFont(size=11), wraplength=320,
                     justify="left").pack(anchor="w", padx=20, pady=(0, 8))

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=20)

        self._lista_scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=6)
        self._lista_scroll.pack(fill="both", expand=True, padx=20, pady=8)

        row_btns = ctk.CTkFrame(self, fg_color="transparent")
        row_btns.pack(anchor="e", padx=20, pady=(0, 16))
        ctk.CTkButton(row_btns, text="Cancelar", width=90, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                      command=self._on_cancelar).pack(side="left", padx=(0, 8))
        self._btn_confirmar = ctk.CTkButton(row_btns, text="Imprimir", width=110, height=32,
                                            fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                                            state="disabled", command=self._confirmar)
        self._btn_confirmar.pack(side="left")

    def _carregar(self):
        try:
            impressoras = self._servico.listar_impressoras(self._usuario.id)
        except Exception as exc:
            logger.error("Erro ao listar impressoras: %s", exc)
            self._banner.erro(f"Erro ao listar impressoras: {exc}")
            return

        if not impressoras:
            ctk.CTkLabel(self._lista_scroll, text="Nenhuma impressora instalada nesta estação.",
                        text_color="#888780", font=ctk.CTkFont(size=11)).pack(pady=16)
            return

        for nome in impressoras:
            ctk.CTkRadioButton(self._lista_scroll, text=nome, variable=self._var_impressora,
                               value=nome, font=ctk.CTkFont(size=12),
                               command=self._ao_selecionar).pack(anchor="w", padx=10, pady=6)

    def _ao_selecionar(self):
        self._btn_confirmar.configure(state="normal")

    def _confirmar(self):
        nome = self._var_impressora.get()
        if not nome:
            self._banner.erro("Selecione uma impressora.")
            return
        self._on_confirmar(nome)
