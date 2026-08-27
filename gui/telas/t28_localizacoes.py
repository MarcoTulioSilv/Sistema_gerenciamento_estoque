"""
gui.telas.t28_localizacoes.py
Tela T-28 — Cadastro de localizações (MOD-07, RF-27) — exclusiva do perfil TI.
"""
import logging
from tkinter import messagebox

import customtkinter as ctk

from gui.componentes.form_widgets import Campo, SecaoFormulario, FeedbackBanner
from Modulo_07_patrimonio import PatrimonioService, PatrimonioError, LocalizacaoEmUsoError

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM,
)

_COLUNAS = [
    ("Setor",       160),
    ("Sala",        160),
    ("Descrição",   300),
    ("Situação",     90),
    ("Bens ativos", 100),
    ("Ações",       140),
]


class TelaLocalizacoes(ctk.CTkFrame):
    """T-28 — cadastro, edição e desativação de localizações (RF-27), exclusiva do TI."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._servico = PatrimonioService()
        self._localizacoes = []  # list[tuple[Localizacao, int]]
        self._painel_edicao = None
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Localizações", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COR_PETROLEO).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(topbar, text="+ Nova localização", width=150, height=28,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      font=ctk.CTkFont(size=15),
                      command=self._abrir_novo).pack(side="right", padx=16, pady=8)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        hdr = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10, 0))
        for col, (txt, larg) in enumerate(_COLUNAS):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=15, weight="bold"),
                         width=larg, anchor="center" if col!=0 else "w").grid(row=0, column=col, padx=6, pady=6, sticky="w")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        try:
            self._localizacoes = self._servico.listar_localizacoes_com_contagem(
                self._usuario.id, apenas_ativas=False)
        except PatrimonioError as exc:
            logger.error("Erro ao carregar localizações: %s", exc)
            self._banner.erro(str(exc))
            return
        self._renderizar()

    def _renderizar(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not self._localizacoes:
            ctk.CTkLabel(self._scroll, text="Nenhuma localização cadastrada.",
                        text_color="#888780").pack(pady=24)
            return

        for i, (loc, total_ativos) in enumerate(self._localizacoes):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            valores = [(loc.setor, 160), (loc.sala, 160), (loc.descricao or "—", 300)]
            for col, (val, larg) in enumerate(valores):
                ctk.CTkLabel(row, text=val, text_color="#3d3d3a", font=ctk.CTkFont(size=15),
                             width=larg , anchor="w").grid(row=0, column=col, padx=6, pady=7, sticky="w")

            fg_s, tc_s = ("#EAF3DE", "#27500A") if loc.ativo else ("#F1EFE8", "#5F5E5A")
            ctk.CTkLabel(row, text="Ativa" if loc.ativo else "Inativa",
                         fg_color=fg_s, text_color=tc_s, font=ctk.CTkFont(size=15, weight="bold"),
                         corner_radius=6, padx=6, pady=2, width=90).grid(row=0, column=3, padx=6, pady=7)

            ctk.CTkLabel(row, text=str(total_ativos), text_color="#3d3d3a",
                         font=ctk.CTkFont(size=15), width=100, anchor="center"
                         ).grid(row=0, column=4, padx=6, pady=7)

            acoes = ctk.CTkFrame(row, fg_color="transparent")
            acoes.grid(row=0, column=5, padx=6, pady=5)
            ctk.CTkButton(acoes, text="Editar", width=65, height=31,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B,
                          hover_color=COR_CINZA_E, font=ctk.CTkFont(size=13),
                          command=lambda l=loc: self._abrir_edicao(l)).pack(side="left", padx=(0, 4))
            if loc.ativo:
                ctk.CTkButton(acoes, text="Desativar", width=65, height=31,
                              fg_color=COR_VERM, hover_color="#7a1f1f",
                              text_color="#fff", font=ctk.CTkFont(size=13),
                              command=lambda l=loc: self._desativar(l)).pack(side="left")

    # ── Painel de edição ──────────────────────────────────────────────────────

    def _abrir_novo(self):
        self._abrir_form(None)

    def _abrir_edicao(self, localizacao):
        self._abrir_form(localizacao)

    def _abrir_form(self, localizacao):
        if self._painel_edicao:
            self._painel_edicao.destroy()
        self._painel_edicao = PainelLocalizacao(
            self, localizacao=localizacao,
            on_salvar=self._ao_salvar, on_cancelar=self._fechar_form,
            servico=self._servico, usuario=self._usuario,
        )
        self._painel_edicao.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5, relheight=0.55)

    def _fechar_form(self):
        if self._painel_edicao:
            self._painel_edicao.destroy()
            self._painel_edicao = None

    def _ao_salvar(self, msg: str):
        self._fechar_form()
        self._banner.sucesso(msg)
        self._carregar()

    # ── Desativar ─────────────────────────────────────────────────────────────

    def _desativar(self, localizacao):
        if not messagebox.askyesno("Confirmar",
                                    f"Desativar '{localizacao.nome_completo}'?", parent=self):
            return
        try:
            self._servico.desativar_localizacao(localizacao.id, usuario_id=self._usuario.id)
            self._banner.sucesso("Localização desativada.")
            self._carregar()
        except LocalizacaoEmUsoError as exc:
            self._banner.erro(str(exc))
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao desativar localização: %s", exc)
            self._banner.erro(f"Erro: {exc}")

    def limpar_memoria(self):
        """Chamado pelo app.py ao sair da tela para esvaziar a RAM."""
        if self._painel_edicao is not None:
            self._painel_edicao.destroy()
            self._painel_edicao = None
        self._localizacoes = None


# ── Painel de cadastro/edição ─────────────────────────────────────────────────

class PainelLocalizacao(ctk.CTkFrame):
    """Painel flutuante de cadastro/edição de localização (T-28), padrão de PainelUsuario (T-15/16)."""

    def __init__(self, master, localizacao, on_salvar, on_cancelar, servico, usuario):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=10,
                         border_width=1, border_color=COR_CINZA_B)
        self._localizacao = localizacao
        self._on_salvar = on_salvar
        self._on_cancelar = on_cancelar
        self._servico = servico
        self._usuario = usuario
        self._construir()
        if localizacao:
            self._campo_setor.set(localizacao.setor)
            self._campo_sala.set(localizacao.sala)
            if localizacao.descricao:
                self._campo_descricao.set(localizacao.descricao)

    def _construir(self):
        titulo = "Editar localização" if self._localizacao else "Nova localização"
        ctk.CTkLabel(self, text=titulo, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COR_PETROLEO).pack(anchor="w", padx=20, pady=(16, 0))

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=20, pady=(8, 0))

        sec = SecaoFormulario(self, titulo="Dados da localização")
        sec.pack(fill="x", padx=20, pady=8)

        self._campo_setor = Campo(sec, "Setor", obrigatorio=True)
        self._campo_setor.pack(fill="x", padx=14, pady=(4, 4))
        self._campo_sala = Campo(sec, "Sala", obrigatorio=True)
        self._campo_sala.pack(fill="x", padx=14, pady=(0, 4))
        self._campo_descricao = Campo(sec, "Descrição", obrigatorio=False)
        self._campo_descricao.pack(fill="x", padx=14, pady=(0, 12))

        row_btns = ctk.CTkFrame(self, fg_color="transparent")
        row_btns.pack(anchor="e", padx=20, pady=(8, 16))
        ctk.CTkButton(row_btns, text="Cancelar", width=90, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=self._on_cancelar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_btns, text="Salvar", width=90, height=32,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      command=self._salvar).pack(side="left")

    def _salvar(self):
        if not self._campo_setor.validar() or not self._campo_sala.validar():
            return
        setor = self._campo_setor.get()
        sala = self._campo_sala.get()
        descricao = self._campo_descricao.get() or None

        try:
            if self._localizacao:
                self._servico.editar_localizacao(
                    self._localizacao.id, setor, sala,
                    usuario_id=self._usuario.id, descricao=descricao)
                msg = f"Localização '{setor} — {sala}' atualizada com sucesso."
            else:
                self._servico.cadastrar_localizacao(
                    setor, sala, usuario_id=self._usuario.id, descricao=descricao)
                msg = f"Localização '{setor} — {sala}' criada com sucesso."
            self._on_salvar(msg)
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao salvar localização: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")
