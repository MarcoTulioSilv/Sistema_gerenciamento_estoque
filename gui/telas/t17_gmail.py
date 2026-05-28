"""
gui.telas.t17_gmail.py
T-17 — Configuração da conta Gmail SMTP (UC-18, RNF-09) — perfil TI.
Toda lógica de persistência e criptografia está em Modulo_05_admin.ConfigService.
"""
import logging

import customtkinter as ctk

from gui.componentes.form_widgets import Campo, SecaoFormulario, FeedbackBanner
from Modulo_05_admin import ConfigService

logger = logging.getLogger(__name__)

COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_BRANCO  = "#FFFFFF"


class TelaGmail(ctk.CTkFrame):
    """T-17 — Configuração da conta Gmail para envio de e-mails."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):

        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text="Configuração Gmail SMTP",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        # Conta de envio
        sec1 = SecaoFormulario(scroll, titulo="Conta de envio (Gmail)")
        sec1.pack(fill="x", padx=16, pady=(12, 0))

        self._campo_usuario = Campo(sec1, "Endereço Gmail (remetente)", obrigatorio=True,
                                    placeholder="sce.clinica@gmail.com")
        self._campo_usuario.pack(fill="x", padx=14, pady=(4, 8))

        ctk.CTkLabel(sec1, text="App Password *",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#888780").pack(anchor="w", padx=14)
        self._entry_senha = ctk.CTkEntry(sec1, show="•", height=32, corner_radius=6,
                                          placeholder_text="Deixe em branco para manter a atual")
        self._entry_senha.pack(fill="x", padx=14, pady=(2, 4))
        ctk.CTkLabel(
            sec1,
            text="Gere em: Conta Google → Segurança → Verificação em 2 etapas → Senhas de app.\n"
                 "Armazenado com criptografia AES-128 (Fernet) — AD-10.",
            text_color="#888780", font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Destinatário
        sec2 = SecaoFormulario(scroll, titulo="Destinatário dos alertas e relatórios")
        sec2.pack(fill="x", padx=16, pady=(10, 0))
        self._campo_destino = Campo(sec2, "E-mail da Gestora (destinatária)", obrigatorio=True,
                                     placeholder="gestora@clinica.com.br")
        self._campo_destino.pack(fill="x", padx=14, pady=(4, 8))

        # Botões
        row_btns = ctk.CTkFrame(scroll, fg_color="transparent")
        row_btns.pack(anchor="e", padx=16, pady=(12, 16))

        ctk.CTkButton(
            row_btns, text="🔌  Testar conexão", width=150, height=36,
            fg_color=COR_BRANCO, text_color=COR_AZUL_M,
            border_width=1, border_color=COR_AZUL_M,
            hover_color=COR_CINZA_E, font=ctk.CTkFont(size=12),
            command=self._testar,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            row_btns, text="Salvar configuração", width=160, height=36,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=12),
            command=self._salvar,
        ).pack(side="left")

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        try:
            cfg = ConfigService.ler_config_gmail()
            self._campo_usuario.set(cfg.get("smtp_usuario", ""))
            self._campo_destino.set(cfg.get("email_destinatario_relatorio", ""))
        except Exception as exc:
            logger.warning("Não foi possível carregar config Gmail: %s", exc)

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _testar(self):
        # Salva primeiro se houver nova senha
        if self._entry_senha.get().strip():
            self._salvar(apenas_persistir=True)
        try:
            msg = ConfigService.testar_conexao_gmail()
            self._banner.sucesso(f"✓ {msg}")
        except Exception as exc:
            self._banner.erro(f"Falha na conexão: {exc}")

    def _salvar(self, apenas_persistir: bool = False):
        usuario = self._campo_usuario.get().strip()
        destino = self._campo_destino.get().strip()
        senha   = self._entry_senha.get().strip()

        try:
            ConfigService.salvar_config_gmail(
                smtp_usuario        = usuario,
                app_password        = senha or None,
                email_destinatario  = destino,
                usuario_id          = self._usuario.id,
            )
            if senha:
                self._entry_senha.delete(0, "end")
            if not apenas_persistir:
                self._banner.sucesso("Configuração Gmail salva com sucesso.")
                logger.info("Config Gmail atualizada por %s.", self._usuario.login)
        except ValueError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao salvar config Gmail: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")
