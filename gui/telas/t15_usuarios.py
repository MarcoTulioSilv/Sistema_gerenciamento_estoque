"""
gui.telas.t15_usuarios.py
T-15 — Listagem de usuários  (UC-09, RF-18) — perfil TI
T-16 — Cadastro / edição / desativação de usuário — painel inline

Toda lógica de negócio (bcrypt, validações, proteção do último TI)
está em Modulo_05_admin.UsuarioService.
"""
import logging
from tkinter import messagebox

import customtkinter as ctk

from gui.componentes.form_widgets import Campo, SecaoFormulario, FeedbackBanner
from Modulo_05_admin import UsuarioService, DadosUsuario
from Modulo_06_dados import PerfilEnum

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM, COR_VERDE,
)

_PERFIS_LABEL = {
    PerfilEnum.tecnico: "Técnico",
    PerfilEnum.admin:   "Administrativo",
    PerfilEnum.ti:      "TI",
}
_LABEL_PERFIL = {v: k for k, v in _PERFIS_LABEL.items()}

_COLUNAS = [
    ("Nome",      200),
    ("Login",     130),
    ("Perfil",    110),
    ("Status",     80),
    ("Criado em", 100),
    ("Ações",     160),
]


class TelaUsuarios(ctk.CTkFrame):
    """T-15 — Listagem e gerenciamento de usuários (perfil TI)."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._painel_edicao: ctk.CTkFrame | None = None
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Gerenciamento de usuários",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(topbar, text="+ Novo usuário", width=130, height=28,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      font=ctk.CTkFont(size=11),
                      command=self._abrir_novo).pack(side="right", padx=16, pady=8)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        hdr = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10, 0))
        for col, (txt, larg) in enumerate(_COLUNAS):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=larg, anchor="w").grid(
                row=0, column=col, padx=6, pady=6, sticky="w")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        try:
            dados = UsuarioService.listar()
            self._renderizar(dados)
        except Exception as exc:
            logger.error("Erro ao carregar usuários: %s", exc)
            self._banner.erro(f"Erro ao carregar: {exc}")

    def _renderizar(self, dados: list[DadosUsuario]):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not dados:
            ctk.CTkLabel(self._scroll, text="Nenhum usuário cadastrado.",
                         text_color="#888780").pack(pady=24)
            return

        ti_ativos = sum(1 for d in dados if d.perfil == PerfilEnum.ti and d.ativo)

        for i, d in enumerate(dados):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            valores = [
                (d.nome[:24],                                      200),
                (d.login,                                          130),
                (_PERFIS_LABEL.get(d.perfil, d.perfil.value),     110),
            ]
            for col, (val, larg) in enumerate(valores):
                ctk.CTkLabel(row, text=val, text_color="#3d3d3a",
                             font=ctk.CTkFont(size=11), width=larg,
                             anchor="w").grid(row=0, column=col, padx=6, pady=7, sticky="w")

            fg_s, tc_s = ("#EAF3DE", "#27500A") if d.ativo else ("#F1EFE8", "#5F5E5A")
            ctk.CTkLabel(row, text="Ativo" if d.ativo else "Inativo",
                         fg_color=fg_s, text_color=tc_s,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         corner_radius=6, padx=6, pady=2, width=80).grid(
                row=0, column=3, padx=6, pady=7)

            ctk.CTkLabel(row, text=d.criado_em, text_color="#888780",
                         font=ctk.CTkFont(size=11), width=100).grid(
                row=0, column=4, padx=6, pady=7)

            frame_ac = ctk.CTkFrame(row, fg_color="transparent")
            frame_ac.grid(row=0, column=5, padx=6, pady=5)

            uid = d.id
            ctk.CTkButton(frame_ac, text="Editar", width=60, height=26,
                          fg_color=COR_BRANCO, text_color="#3d3d3a",
                          border_width=1, border_color=COR_CINZA_B,
                          hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                          command=lambda u=uid: self._abrir_edicao(u),
                          ).pack(side="left", padx=(0, 4))

            eh_unico_ti = (d.perfil == PerfilEnum.ti and d.ativo and ti_ativos <= 1)
            if d.ativo:
                ctk.CTkButton(frame_ac, text="Desativar", width=78, height=26,
                              fg_color=COR_VERM, hover_color="#7a1f1f",
                              text_color="#fff", font=ctk.CTkFont(size=11),
                              state="disabled" if eh_unico_ti else "normal",
                              command=lambda u=uid: self._toggle(u, False),
                              ).pack(side="left")
            else:
                ctk.CTkButton(frame_ac, text="Reativar", width=78, height=26,
                              fg_color=COR_VERDE, hover_color="#0F6E56",
                              text_color="#fff", font=ctk.CTkFont(size=11),
                              command=lambda u=uid: self._toggle(u, True),
                              ).pack(side="left")

    # ── Painel de edição ──────────────────────────────────────────────────────

    def _abrir_novo(self):
        self._abrir_form(None)

    def _abrir_edicao(self, usuario_id: int):
        self._abrir_form(usuario_id)

    def _abrir_form(self, usuario_id: int | None):
        if self._painel_edicao:
            self._painel_edicao.destroy()
        self._painel_edicao = PainelUsuario(
            self,
            usuario_id  = usuario_id,
            on_salvar   = self._ao_salvar,
            on_cancelar = self._fechar_form,
        )
        self._painel_edicao.place(relx=0.5, rely=0.5, anchor="center",
                                   relwidth=0.72, relheight=0.85)

    def _fechar_form(self):
        if self._painel_edicao:
            self._painel_edicao.destroy()
            self._painel_edicao = None

    def _ao_salvar(self, msg: str):
        self._fechar_form()
        self._banner.sucesso(msg)
        self._carregar()

    # ── Ativar / Desativar — via UsuarioService ───────────────────────────────

    def _toggle(self, usuario_id: int, ativar: bool):
        acao = "reativar" if ativar else "desativar"
        if not messagebox.askyesno("Confirmar",
                                    f"Deseja {acao} este usuário?",
                                    parent=self):
            return
        try:
            if ativar:
                UsuarioService.reativar(usuario_id)
            else:
                UsuarioService.desativar(usuario_id)
            self._banner.sucesso(f"Usuário {'reativado' if ativar else 'desativado'}.")
            self._carregar()
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao alterar status: %s", exc)
            self._banner.erro(f"Erro: {exc}")


# ── Painel T-16 ───────────────────────────────────────────────────────────────

class PainelUsuario(ctk.CTkFrame):
    """T-16 — Formulário de criação / edição de usuário (usa UsuarioService)."""

    def __init__(self, master, usuario_id: int | None, on_salvar, on_cancelar):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=10,
                         border_width=1, border_color=COR_CINZA_B)
        self._usuario_id  = usuario_id
        self._on_salvar   = on_salvar
        self._on_cancelar = on_cancelar
        self._construir()
        if usuario_id:
            self._carregar(usuario_id)

    def _construir(self):
        titulo = "Editar usuário" if self._usuario_id else "Novo usuário"
        ctk.CTkLabel(self, text=titulo,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w", padx=20, pady=(16, 0))

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=20, pady=(8, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=20, pady=8)

        sec1 = SecaoFormulario(scroll, titulo="Dados do usuário")
        sec1.pack(fill="x", pady=(0, 10))

        self._campo_nome  = Campo(sec1, "Nome completo", obrigatorio=True)
        self._campo_nome.pack(fill="x", padx=14, pady=(4, 4))

        self._campo_login = Campo(sec1, "Login", obrigatorio=True)
        self._campo_login.pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkLabel(sec1, text="Perfil *",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#888780").pack(anchor="w", padx=14)
        self._opt_perfil = ctk.CTkOptionMenu(
            sec1, values=list(_LABEL_PERFIL.keys()),
            width=200, height=32, corner_radius=6,
            fg_color=COR_CINZA_E, button_color=COR_AZUL_M, text_color="#3d3d3a",
            command=self._ao_mudar_perfil,
        )
        self._opt_perfil.set("Técnico")
        self._opt_perfil.pack(anchor="w", padx=14, pady=(2, 8))

        sec_patrim = SecaoFormulario(scroll, titulo="Acesso ao Patrimônio")
        sec_patrim.pack(fill="x", pady=(0, 10))

        self._var_patrimonio = ctk.BooleanVar(value=False)
        self._chk_patrimonio = ctk.CTkCheckBox(
            sec_patrim, text="Acesso ao módulo de Patrimônio",
            variable=self._var_patrimonio,
            text_color="#3d3d3a", font=ctk.CTkFont(size=12),
        )
        self._chk_patrimonio.pack(anchor="w", padx=14, pady=(0, 4))

        self._lbl_nota_patrim = ctk.CTkLabel(
            sec_patrim, text="", text_color="#888780",
            font=ctk.CTkFont(size=10), anchor="w")
        self._lbl_nota_patrim.pack(anchor="w", padx=14, pady=(0, 10))

        self._ao_mudar_perfil(self._opt_perfil.get())

        sec2 = SecaoFormulario(scroll, titulo="Senha")
        sec2.pack(fill="x", pady=(0, 10))

        aviso = "(deixe em branco para não alterar)" if self._usuario_id else "(obrigatória)"
        ctk.CTkLabel(sec2, text=f"Nova senha {aviso}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#888780").pack(anchor="w", padx=14, pady=(4, 0))
        self._entry_senha = ctk.CTkEntry(sec2, show="•", height=32, corner_radius=6)
        self._entry_senha.pack(fill="x", padx=14, pady=(2, 4))

        ctk.CTkLabel(sec2, text="Confirmar nova senha",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#888780").pack(anchor="w", padx=14)
        self._entry_conf = ctk.CTkEntry(sec2, show="•", height=32, corner_radius=6)
        self._entry_conf.pack(fill="x", padx=14, pady=(2, 4))

        ctk.CTkLabel(sec2, text="Mínimo 8 caracteres.",
                     text_color="#888780", font=ctk.CTkFont(size=10)).pack(
            anchor="w", padx=14, pady=(0, 8))

        row_btns = ctk.CTkFrame(self, fg_color="transparent")
        row_btns.pack(anchor="e", padx=20, pady=(0, 16))
        ctk.CTkButton(row_btns, text="Cancelar", width=90, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=self._on_cancelar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_btns, text="Salvar", width=90, height=32,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      command=self._salvar).pack(side="left")

    def _ao_mudar_perfil(self, perfil_label: str):
        """TI acessa o Patrimônio por definição (RF-39) — checkbox fica travada nesse caso."""
        eh_ti = _LABEL_PERFIL.get(perfil_label) == PerfilEnum.ti
        if eh_ti:
            self._chk_patrimonio.configure(state="disabled")
            self._lbl_nota_patrim.configure(text="TI tem acesso automático, independente desta opção.")
        else:
            self._chk_patrimonio.configure(state="normal")
            self._lbl_nota_patrim.configure(text="Concessão exclusiva do perfil TI (RN-22).")

    def _carregar(self, uid: int):
        try:
            dados = UsuarioService.buscar(uid)
            if dados:
                self._campo_nome.set(dados.nome)
                self._campo_login.set(dados.login)
                self._opt_perfil.set(_PERFIS_LABEL.get(dados.perfil, dados.perfil.value))
                self._var_patrimonio.set(dados.acesso_patrimonio)
                self._ao_mudar_perfil(self._opt_perfil.get())
        except Exception as exc:
            self._banner.erro(f"Erro ao carregar: {exc}")

    def _salvar(self):
        nome      = self._campo_nome.get().strip()
        login     = self._campo_login.get().strip()
        perfil_lb = self._opt_perfil.get()
        senha     = self._entry_senha.get()
        conf      = self._entry_conf.get()

        if senha and senha != conf:
            self._banner.erro("Senhas não conferem.")
            return

        perfil_enum = _LABEL_PERFIL.get(perfil_lb)
        if not perfil_enum:
            self._banner.erro("Selecione um perfil válido.")
            return

        acesso_patrimonio = self._var_patrimonio.get()

        try:
            if self._usuario_id:
                UsuarioService.editar(
                    usuario_id = self._usuario_id,
                    nome       = nome,
                    login      = login,
                    perfil     = perfil_enum,
                    nova_senha = senha or None,
                    acesso_patrimonio = acesso_patrimonio,
                )
                msg = f"Usuário '{nome}' atualizado com sucesso."
            else:
                UsuarioService.criar(
                    nome   = nome,
                    login  = login,
                    senha  = senha,
                    perfil = perfil_enum,
                    acesso_patrimonio = acesso_patrimonio,
                )
                msg = f"Usuário '{nome}' criado com sucesso."

            self._on_salvar(msg)

        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao salvar usuário: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")

    def limpar_memoria(self):
        """Garante o fechamento do painel de edição flutuante, se aberto."""
        if hasattr(self, '_painel_edicao') and self._painel_edicao is not None:
            self._painel_edicao.destroy()
            self._painel_edicao = None