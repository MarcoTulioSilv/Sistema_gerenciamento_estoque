"""
gui · telas · t12_agendamento.py
Tela T-12 — Configuração de agendamento de relatórios (UC-10, RF-21).
Apenas TI. Permite habilitar/desabilitar e configurar periodicidade e horário.
"""
import logging
from datetime import time
from Modulo_03_relatorios import RelatorioService
import customtkinter as ctk
from gui.componentes.form_widgets import FeedbackBanner

logger = logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERDE  = "#1D9E75"
COR_VERM   = "#A32D2D"

PERIODICIDADES = ["diario", "semanal", "mensal"]

# Tipos e seus rótulos
_TIPOS = [
    ("movimentacao",   "Relatório de movimentação",         False),
    ("estoque_atual",  "Relatório de estoque atual",         False),
    ("a_vencer",       "Produtos próximos ao vencimento",    False),
    ("lotes_vencidos", "Lotes vencidos em estoque",          True),
    # True = obrigatório (RF-22), toggle bloqueado
]


class TelaAgendamento(ctk.CTkFrame):
    """Configuração de envio automático de relatórios por tipo."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._linhas: list[_LinhaAgendamento] = []
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text="Agendamento de relatórios",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        # Card principal
        card = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=8,
                             border_width=1, border_color=COR_CINZA_B)
        card.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(card, text="Configurar envio automático por tipo de relatório",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkFrame(card, fg_color=COR_CINZA_B, height=1).pack(
            fill="x", padx=14, pady=(6, 0))

        # Uma linha por tipo de relatório
        for tipo, rotulo, obrigatorio in _TIPOS:
            linha = _LinhaAgendamento(card, tipo=tipo, rotulo=rotulo,
                                      obrigatorio=obrigatorio)
            linha.pack(fill="x", padx=14, pady=2)
            self._linhas.append(linha)

        # Aviso sobre scheduler
        aviso = ctk.CTkFrame(card, fg_color="#FAEEDA", corner_radius=6,
                              border_width=1, border_color="#EF9F27")
        aviso.pack(fill="x", padx=14, pady=(8, 14))
        ctk.CTkLabel(aviso,
                     text="⚠  Notificações e relatórios automáticos só são disparados "
                          "enquanto o SCE estiver aberto em alguma estação (Risco R-01).\n"
                          "Recomenda-se deixar o SCE aberto na máquina do TI ou servidor.",
                     text_color="#854F0B", font=ctk.CTkFont(size=10),
                     justify="left", anchor="w", wraplength=700).pack(
            fill="x", padx=10, pady=8)

        # Botões
        row_btns = ctk.CTkFrame(self, fg_color="transparent")
        row_btns.pack(anchor="e", padx=16, pady=(0, 16))
        ctk.CTkButton(row_btns, text="Cancelar", width=100, height=34,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=lambda: self._on_navigate("relatorios")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_btns, text="Salvar agendamentos", width=170, height=34,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      command=self._salvar).pack(side="left")

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        try:
            
            ags = {a.tipo_relatorio: a for a in RelatorioService.listar_agendamentos()}
            for linha in self._linhas:
                ag = ags.get(linha.tipo)
                if ag:
                    linha.preencher(ag.habilitado, ag.periodicidade,
                                    ag.horario if isinstance(ag.horario, time)
                                    else time(7, 0))
        except Exception as exc:
            logger.error("Erro ao carregar agendamentos: %s", exc)
            self._banner.erro(f"Erro ao carregar: {exc}")

    def _salvar(self):
        try:
            for linha in self._linhas:
                hab, per, hor = linha.obter_valores()
                RelatorioService.salvar_agendamento(linha.tipo, hab, per, hor)
            self._banner.sucesso("Agendamentos salvos com sucesso.")
        except Exception as exc:
            logger.error("Erro ao salvar agendamentos: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")


# ── Componente de linha ───────────────────────────────────────────────────────

class _LinhaAgendamento(ctk.CTkFrame):
    """Uma linha de configuração de agendamento com toggle, periodicidade e horário."""

    def __init__(self, master, tipo: str, rotulo: str, obrigatorio: bool, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.tipo        = tipo
        self._obrigatorio = obrigatorio

        # Separador superior
        ctk.CTkFrame(self, fg_color="#E8E6DE", height=1).pack(fill="x", pady=(0, 8))

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="x")
        corpo.grid_columnconfigure(0, weight=1)

        # Coluna esquerda: título e detalhe
        info = ctk.CTkFrame(corpo, fg_color="transparent")
        info.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(info, text=rotulo,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#3d3d3a", anchor="w").pack(anchor="w")

        self._lbl_detalhe = ctk.CTkLabel(
            info, text="Desabilitado — último envio: nunca",
            font=ctk.CTkFont(size=10), text_color="#888780", anchor="w")
        self._lbl_detalhe.pack(anchor="w")

        # Coluna direita: periodicidade + horário + toggle
        controles = ctk.CTkFrame(corpo, fg_color="transparent")
        controles.grid(row=0, column=1, sticky="e", padx=8)

        self._opt_per = ctk.CTkOptionMenu(
            controles, values=PERIODICIDADES,
            width=100, height=28, corner_radius=4,
            fg_color="#F2F1ED", button_color=COR_AZUL_M,
            text_color="#3d3d3a", font=ctk.CTkFont(size=11))
        self._opt_per.pack(side="left", padx=(0, 8))
        self._opt_per.set("diario")

        self._entry_hora = ctk.CTkEntry(
            controles, placeholder_text="07:00",
            width=70, height=28, corner_radius=4)
        self._entry_hora.pack(side="left", padx=(0, 12))
        self._entry_hora.insert(0, "07:00")

        # Toggle on/off
        self._toggle_var = ctk.BooleanVar(value=False)
        self._toggle_btn = ctk.CTkSwitch(
            controles, text="", variable=self._toggle_var,
            width=46, height=24,
            button_color=COR_VERDE, progress_color=COR_VERDE,
            command=self._ao_mudar_toggle)
        self._toggle_btn.pack(side="left")

        if obrigatorio:
            # RF-22: lotes vencidos sempre habilitado, toggle bloqueado
            self._toggle_var.set(True)
            self._toggle_btn.configure(state="disabled")
            self._opt_per.set("diario")
            self._opt_per.configure(state="disabled")
            self._lbl_detalhe.configure(
                text="Automático diário — não pode ser desabilitado (RF-22)")

        self._atualizar_estado()

    def _ao_mudar_toggle(self):
        self._atualizar_estado()

    def _atualizar_estado(self):
        habilitado = self._toggle_var.get()
        estado = "normal" if habilitado else "disabled"
        if not self._obrigatorio:
            self._opt_per.configure(state=estado)
            self._entry_hora.configure(state=estado)

    def preencher(self, habilitado: bool, periodicidade: str, horario: time):
        if not self._obrigatorio:
            self._toggle_var.set(habilitado)
        self._opt_per.set(periodicidade)
        hor_str = horario.strftime("%H:%M") if hasattr(horario, "strftime") else "07:00"
        self._entry_hora.delete(0, "end")
        self._entry_hora.insert(0, hor_str)
        self._atualizar_estado()

    def obter_valores(self) -> tuple[bool, str, time]:
        habilitado   = self._toggle_var.get()
        periodicidade= self._opt_per.get()
        hor_txt      = self._entry_hora.get().strip() or "07:00"
        try:
            partes = hor_txt.split(":")
            horario = time(int(partes[0]), int(partes[1]))
        except Exception:
            horario = time(7, 0)
        return habilitado, periodicidade, horario