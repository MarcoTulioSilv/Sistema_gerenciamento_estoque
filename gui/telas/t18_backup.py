"""
gui.telas.t18_backup.py
T-18 — Backup do banco de dados (UC-19, RNF-04) — perfil TI.
Toda lógica de execução e log está em Modulo_05_admin.BackupManager.
"""
import logging
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gui.componentes.form_widgets import FeedbackBanner, SecaoFormulario
from Modulo_05_admin import BackupManager

logger = logging.getLogger(__name__)

COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_BRANCO  = "#FFFFFF"


class TelaBackup(ctk.CTkFrame):
    """T-18 — Backup manual e informações sobre backup automático."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._em_execucao = False
        self._manager     = BackupManager()
        self._construir()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Backup do banco de dados",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        # ── Backup manual ─────────────────────────────────────────────────────
        sec1 = SecaoFormulario(scroll, titulo="Backup manual")
        sec1.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            sec1,
            text="Gera um arquivo .sql via mysqldump no diretório selecionado.\n"
                 "O arquivo é nomeado automaticamente: sce_db_YYYYMMDD_HHMMSS.sql",
            text_color="#5F5E5A", font=ctk.CTkFont(size=12),
            justify="left", anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 10))

        row_dir = ctk.CTkFrame(sec1, fg_color="transparent")
        row_dir.pack(fill="x", padx=14, pady=(0, 8))
        row_dir.grid_columnconfigure(0, weight=1)

        self._entry_dir = ctk.CTkEntry(row_dir, height=32, corner_radius=6,
                                        placeholder_text="Diretório de destino")
        self._entry_dir.insert(0, str(Path(".") / "backups"))
        self._entry_dir.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(row_dir, text="Escolher...", width=90, height=32,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._escolher_dir).grid(row=0, column=1)

        self._btn_backup = ctk.CTkButton(
            sec1, text="▶  Executar backup agora",
            width=200, height=36,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            font=ctk.CTkFont(size=12),
            command=self._executar,
        )
        self._btn_backup.pack(anchor="w", padx=14, pady=(0, 4))

        self._progress = ctk.CTkProgressBar(sec1, mode="indeterminate")
        # Oculto até iniciar backup

        # ── Aviso risco R-01 ──────────────────────────────────────────────────
        sec2 = SecaoFormulario(scroll, titulo="Backup automático")
        sec2.pack(fill="x", padx=16, pady=(10, 0))

        aviso = ctk.CTkFrame(sec2, fg_color="#FAEEDA", corner_radius=6,
                             border_width=1, border_color="#EF9F27")
        aviso.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkLabel(
            aviso,
            text="⚠  O backup automático só é executado enquanto o SCE estiver aberto\n"
                 "    (risco R-01 do DAS). Recomenda-se manter o SCE aberto ou agendar\n"
                 "    o mysqldump diretamente no servidor via Agendador de Tarefas do Windows.",
            text_color="#633806", font=ctk.CTkFont(size=11),
            justify="left", anchor="w",
        ).pack(fill="x", padx=12, pady=8)

        # ── Instrução de restauração ──────────────────────────────────────────
        sec3 = SecaoFormulario(scroll, titulo="Restauração")
        sec3.pack(fill="x", padx=16, pady=(10, 16))
        ctk.CTkLabel(
            sec3,
            text="A restauração é feita diretamente via MySQL Workbench:\n"
                 "  1. Conecte ao servidor  sce_db.\n"
                 "  2. Menu: Server → Data Import → Import from Self-Contained File.\n"
                 "  3. Selecione o arquivo .sql gerado nesta tela.",
            text_color="#5F5E5A", font=ctk.CTkFont(size=11),
            justify="left", anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 12))

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _escolher_dir(self):
        d = filedialog.askdirectory(title="Selecionar diretório de backup")
        if d:
            self._entry_dir.delete(0, "end")
            self._entry_dir.insert(0, d)

    def _executar(self):
        if self._em_execucao:
            return
        diretorio = self._entry_dir.get().strip()
        if not diretorio:
            self._banner.erro("Selecione o diretório de destino.")
            return

        self._em_execucao = True
        self._btn_backup.configure(state="disabled")
        self._progress.pack(anchor="w", padx=14, pady=(4, 8))
        self._progress.start()
        self._banner.aviso("Executando backup...")

        # BackupManager roda em thread daemon e chama os callbacks na conclusão.
        # Os callbacks são chamados da thread do backup — usamos self.after()
        # para garantir execução na thread principal do Tkinter.
        self._manager.executar(
            diretorio  = Path(diretorio),
            on_sucesso = lambda msg: self.after(0, lambda: self._finalizar(msg, True)),
            on_erro    = lambda msg: self.after(0, lambda: self._finalizar(msg, False)),
        )

    def _finalizar(self, msg: str, sucesso: bool):
        self._em_execucao = False
        self._btn_backup.configure(state="normal")
        self._progress.stop()
        self._progress.pack_forget()
        if sucesso:
            self._banner.sucesso(msg)
        else:
            self._banner.erro(msg)

    def _exibir_erro(self, mensagem):
        """Injeta o banner na interface, logo abaixo da topbar, e exibe o erro."""
        self._banner.pack(after=self._topbar, fill="x", padx=16, pady=(8, 0))
        self._banner.erro(mensagem)
    
    def _ocultar_banner(self):
        """Remove o banner da interface, devolvendo o espaço vazio."""
        self._banner.pack_forget()