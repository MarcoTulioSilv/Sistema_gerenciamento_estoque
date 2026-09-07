"""
gui.telas.t29_historico_manutencao.py
Tela T-29 — Histórico de manutenção de um bem (MOD-07, RF-38).
Painel flutuante, aberto pela ficha do bem em T-25 — não é rota nem item de menu.
"""
import logging
from datetime import datetime

import customtkinter as ctk

from gui.componentes.form_widgets import Campo, FeedbackBanner
from Modulo_07_patrimonio import PatrimonioService, DadosManutencao, PatrimonioError

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO,
)


class PainelHistoricoManutencao(ctk.CTkFrame):
    """T-29 — histórico de manutenção de um bem + registro de nova manutenção (RF-38)."""

    def __init__(self, master, servico: PatrimonioService, usuario, bem, on_fechar):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=10,
                         border_width=1, border_color=COR_CINZA_B)
        self._servico = servico
        self._usuario = usuario
        self._bem = bem
        self._on_fechar = on_fechar
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(topo, text="Histórico de manutenção", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COR_PETROLEO).pack(side="left")
        ctk.CTkButton(topo, text="Fechar", width=70, height=26,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._on_fechar).pack(side="right")

        ctk.CTkLabel(self, text=f"{self._bem.tombo} — {self._bem.descricao}",
                     text_color="#888780", font=ctk.CTkFont(size=11), anchor="w"
                     ).pack(fill="x", padx=20, pady=(0, 8))

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=20)

        # ── Registrar nova manutenção ───────────────────────────────────────────
        form = ctk.CTkFrame(self, fg_color=COR_CINZA_E, corner_radius=8)
        form.pack(fill="x", padx=20, pady=(4, 10))
        ctk.CTkLabel(form, text="Registrar nova manutenção", text_color=COR_PETROLEO,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self._campo_data = Campo(form, "Data", largura=140)
        self._campo_data.pack(anchor="w", padx=12)
        self._campo_data.set(datetime.now().strftime("%d/%m/%Y"))

        ctk.CTkLabel(form, text="Descrição*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(anchor="w", padx=12, pady=(8, 3))
        self._txt_descricao = ctk.CTkTextbox(form, height=50, corner_radius=6, fg_color=COR_BRANCO)
        self._txt_descricao.pack(fill="x", padx=12)

        ctk.CTkButton(form, text="Registrar", width=120, height=30,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      command=self._registrar).pack(anchor="e", padx=12, pady=10)

        # ── Lista cronológica ────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="HISTÓRICO", text_color=COR_PETROLEO,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=20, pady=(0, 4))
        self._lista_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._lista_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 16))

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        for w in self._lista_scroll.winfo_children():
            w.destroy()
        try:
            historico = self._servico.historico_manutencao(self._usuario.id, self._bem.id)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return

        if not historico:
            ctk.CTkLabel(self._lista_scroll, text="Nenhuma manutenção registrada.",
                        text_color="#888780", font=ctk.CTkFont(size=11)).pack(pady=12)
            return

        for m in reversed(historico):
            item = ctk.CTkFrame(self._lista_scroll, fg_color=COR_CINZA_E, corner_radius=6)
            item.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(item, text=m.data_manutencao.strftime("%d/%m/%Y"),
                         text_color=COR_PETROLEO, font=ctk.CTkFont(size=11, weight="bold"),
                         anchor="w").pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(item, text=m.descricao, text_color="#3d3d3a",
                         font=ctk.CTkFont(size=11), anchor="w", justify="left",
                         wraplength=380).pack(anchor="w", padx=10, pady=(2, 2))
            usuario_str = m.usuario.nome if m.usuario else "—"
            ctk.CTkLabel(item, text=f"Registrado por {usuario_str}",
                         text_color="#888780", font=ctk.CTkFont(size=10), anchor="w"
                         ).pack(anchor="w", padx=10, pady=(0, 8))

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _registrar(self):
        data_texto = self._campo_data.get()
        descricao = self._txt_descricao.get("1.0", "end").strip()

        if not descricao:
            self._banner.erro("Descrição é obrigatória.")
            return
        try:
            data_manutencao = datetime.strptime(data_texto, "%d/%m/%Y").date()
        except ValueError:
            self._banner.erro("Data inválida. Use dd/mm/aaaa.")
            return

        dados = DadosManutencao(data_manutencao=data_manutencao, descricao=descricao)
        try:
            self._servico.registrar_manutencao(self._bem.id, dados, usuario_id=self._usuario.id)
            self._banner.sucesso("Manutenção registrada com sucesso.")
            self._txt_descricao.delete("1.0", "end")
            self._carregar()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao registrar manutenção: %s", exc)
            self._banner.erro(f"Erro ao registrar: {exc}")
