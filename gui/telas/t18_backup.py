"""
gui.telas.t18_backup.py
T-18 — Backup do banco de dados (UC-19, RNF-04) — perfil TI.
Toda lógica de execução e log está em Modulo_05_admin.BackupManager.
"""
import logging
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from zoneinfo import ZoneInfo
import customtkinter as ctk

from gui.componentes.form_widgets import FeedbackBanner, SecaoFormulario
from Modulo_05_admin import BackupManager
from Modulo_04_notificacoes import NotificacaoService

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM, COR_VERDE,
)

_JOB_NOME_BACKUP_SERVIDOR = "backup_automatico_servidor"


def _fmt_utc_local(dt: datetime) -> str:
    """Converte um datetime UTC (naive) vindo do banco para horário local formatado."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")


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

        # ── Backup automático (servidor) ──────────────────────────────────────
        sec2 = SecaoFormulario(scroll, titulo="Backup automático (servidor)")
        sec2.pack(fill="x", padx=16, pady=(10, 0))

        info = ctk.CTkFrame(sec2, fg_color="#EAF3DE", corner_radius=6,
                             border_width=1, border_color=COR_VERDE)
        info.pack(fill="x", padx=14, pady=(4, 10))
        ctk.CTkLabel(
            info,
            text="✓  Backup diário automático configurado no servidor via Agendador de\n"
                 "    Tarefas do Windows (06:30), independente do SCE estar aberto —\n"
                 "    mitiga o risco R-01 do DAS. Histórico das últimas execuções abaixo.",
            text_color="#155724", font=ctk.CTkFont(size=11),
            justify="left", anchor="w",
        ).pack(fill="x", padx=12, pady=8)

        row_hist_hdr = ctk.CTkFrame(sec2, fg_color="transparent")
        row_hist_hdr.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(row_hist_hdr, text="ÚLTIMAS EXECUÇÕES", text_color="#888780",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        ctk.CTkButton(row_hist_hdr, text="Atualizar", width=80, height=24,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=10),
                      command=self._carregar_historico_automatico).pack(side="right")

        self._frame_historico = ctk.CTkFrame(sec2, fg_color=COR_BRANCO, corner_radius=6,
                                              border_width=1, border_color=COR_CINZA_B)
        self._frame_historico.pack(fill="x", padx=14, pady=(0, 12))

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

        self._carregar_historico_automatico()

    # ── Histórico do backup automático ──────────────────────────────────────

    def _carregar_historico_automatico(self):
        for w in self._frame_historico.winfo_children():
            w.destroy()

        try:
            logs = NotificacaoService.listar_job_logs_por_nome(_JOB_NOME_BACKUP_SERVIDOR, limite=10)
            registros = [
                (r.executado_em, r.sucesso, r.detalhe) for r in logs
            ]
        except Exception as exc:
            logger.error("Erro ao carregar histórico de backup automático: %s", exc)
            ctk.CTkLabel(
                self._frame_historico,
                text=f"Não foi possível carregar o histórico: {exc}",
                text_color=COR_VERM, font=ctk.CTkFont(size=11),
                wraplength=560, justify="left", anchor="w",
            ).pack(fill="x", padx=10, pady=10)
            return

        if not registros:
            ctk.CTkLabel(
                self._frame_historico,
                text="Nenhuma execução registrada ainda. Verifique se a tarefa "
                     "agendada foi configurada no servidor (ver backup_script/).",
                text_color="#888780", font=ctk.CTkFont(size=11),
                wraplength=560, justify="left", anchor="w",
            ).pack(fill="x", padx=10, pady=10)
            return

        for i, (executado_em, sucesso, detalhe) in enumerate(registros):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._frame_historico, fg_color=bg, corner_radius=0)
            row.pack(fill="x")
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text=_fmt_utc_local(executado_em), text_color="#3d3d3a",
                         font=ctk.CTkFont(size=11), width=140, anchor="w"
                         ).grid(row=0, column=0, padx=(10, 4), pady=6, sticky="w")

            ctk.CTkLabel(row, text=(detalhe or ""), text_color="#5F5E5A",
                         font=ctk.CTkFont(size=11), anchor="w", justify="left"
                         ).grid(row=0, column=1, padx=4, pady=6, sticky="w")

            status_txt = "Sucesso" if sucesso else "Falha"
            fg_status  = COR_VERDE if sucesso else COR_VERM
            bg_status  = "#EAF3DE" if sucesso else "#FCEBEB"
            ctk.CTkLabel(row, text=status_txt, fg_color=bg_status, text_color=fg_status,
                         font=ctk.CTkFont(size=9, weight="bold"), corner_radius=6,
                         padx=6, pady=2, width=70
                         ).grid(row=0, column=2, padx=(4, 10), pady=6)

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
            logger.error("Erro ao finalizar backup=%s ", msg)
    