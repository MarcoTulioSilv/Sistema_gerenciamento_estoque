"""
gui.telas.t19_log.py
T-19 — Log de operações (UC-20, RNF-06) — perfil TI.
Exibe movimentações, alertas e jobs do scheduler com filtros por período e usuário.
"""
import logging
from datetime import date, datetime, timedelta

import customtkinter as ctk
from sqlalchemy.orm import joinedload

from gui.componentes.form_widgets import FeedbackBanner
from Modulo_06_dados import get_read_session, Movimentacao, NotificacaoLog, JobLog, Usuario, Lote

logger = logging.getLogger(__name__)

COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_BRANCO  = "#FFFFFF"
COR_VERM    = "#A32D2D"
COR_VERDE   = "#1D9E75"
COR_AMBER   = "#BA7517"

_TIPOS_FILTRO = [
    "Todas as operações",
    "Entradas",
    "Saídas",
    "Transferências",
    "Baixas (vencido)",
    "Alertas enviados",
    "Jobs scheduler",
]

_COLUNAS_MOV = [
    ("Data/Hora",    120),
    ("Usuário",      110),
    ("Operação",     120),
    ("Produto/Lote", 200),
    ("Qtd",           50),
    ("Nº NF",         80),
    ("Observação",   200),
    ("Resultado",     80),
]


class TelaLog(ctk.CTkFrame):
    """T-19 — Log de operações do sistema (somente leitura)."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._linhas: list[dict] = []
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text="Log de operações",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(self._topbar, text="Atualizar", width=90, height=28,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._carregar).pack(side="right", padx=16, pady=8)

        self._banner = FeedbackBanner(self)

        # Filtros
        filt = ctk.CTkFrame(self, fg_color="transparent")
        filt.pack(fill="x", padx=16, pady=(8, 0))

        ctk.CTkLabel(filt, text="De:", font=ctk.CTkFont(size=12)).pack(side="left")
        self._entry_ini = ctk.CTkEntry(filt, width=100, height=30, corner_radius=6,
                                        placeholder_text="DD/MM/AAAA")
        self._entry_ini.insert(0, (date.today() - timedelta(days=7)).strftime("%d/%m/%Y"))
        self._entry_ini.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(filt, text="Até:", font=ctk.CTkFont(size=12)).pack(side="left")
        self._entry_fim = ctk.CTkEntry(filt, width=100, height=30, corner_radius=6,
                                        placeholder_text="DD/MM/AAAA")
        self._entry_fim.insert(0, date.today().strftime("%d/%m/%Y"))
        self._entry_fim.pack(side="left", padx=(4, 12))

        self._opt_tipo = ctk.CTkOptionMenu(
            filt, values=_TIPOS_FILTRO, width=180, height=30, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#3d3d3a",
        )
        self._opt_tipo.set("Todas as operações")
        self._opt_tipo.pack(side="left", padx=(0, 8))

        self._entry_busca = ctk.CTkEntry(filt, width=180, height=30, corner_radius=6,
                                          placeholder_text="Buscar produto/usuário...")
        self._entry_busca.pack(side="left", padx=(0, 8))
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        ctk.CTkButton(filt, text="Filtrar", width=80, height=30,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      font=ctk.CTkFont(size=11),
                      command=self._carregar).pack(side="left")

        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(8, 0))
        hdr.grid_columnconfigure(3, weight=1)  # Detalhe é a coluna que expande

        for col, (txt, larg) in enumerate(_COLUNAS_MOV):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=larg, anchor="w").grid(
                row=0, column=col, padx=4, pady=5, sticky="w")
        ctk.CTkLabel(hdr, text="", width=10).grid(row=0, column=len(_COLUNAS_MOV), padx=4)  # Espaço extra no fim
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E,
                                               corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        # Rodapé
        self._lbl_rodape = ctk.CTkLabel(
            self, text="", text_color="#888780", font=ctk.CTkFont(size=10))
        self._lbl_rodape.pack(anchor="w", padx=16, pady=(0, 8))

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _parse_data(self, entry: ctk.CTkEntry) -> date | None:
        txt = entry.get().strip()
        try:
            return datetime.strptime(txt, "%d/%m/%Y").date()
        except ValueError:
            return None

    def _carregar(self):
        self._banner._ocultar()
        
        dt_ini = self._parse_data(self._entry_ini)
        dt_fim = self._parse_data(self._entry_fim)
        if not dt_ini or not dt_fim:
            self._banner.erro("Datas inválidas. Use DD/MM/AAAA.")
            return
        if dt_ini > dt_fim:
            self._banner.erro("Data inicial deve ser anterior à data final.")
            return

        tipo_sel = self._opt_tipo.get()
        linhas: list[dict] = []

        try:
            ini_dt = datetime.combine(dt_ini, datetime.min.time())
            fim_dt = datetime.combine(dt_fim, datetime.max.time())

            with get_read_session() as s:
                # Movimentações
                if tipo_sel in ("Todas as operações", "Entradas", "Saídas",
                                "Transferências", "Baixas (vencido)"):
                    movs = (
                        s.query(Movimentacao)
                        .options(
                            joinedload(Movimentacao.usuario),
                            joinedload(Movimentacao.lote).joinedload(Lote.produto),
                        )
                        .filter(Movimentacao.data_hora.between(ini_dt, fim_dt))
                        .order_by(Movimentacao.data_hora.desc())
                        .limit(500)
                        .all()
                    )
                    _TIPO_LABEL = {
                        "entrada_manual": "Entrada manual",
                        "entrada_nfe":    "Entrada NF-e",
                        "entrada_danfe":  "Entrada DANFE",
                        "saida":          "Saída",
                        "transferencia":  "Transferência",
                        "baixa_vencido":  "Baixa (vencido)",
                    }
                    _FILTRO_TIPO = {
                        "Entradas":          {"entrada_manual", "entrada_nfe", "entrada_danfe"},
                        "Saídas":            {"saida"},
                        "Transferências":    {"transferencia"},
                        "Baixas (vencido)":  {"baixa_vencido"},
                    }
                    tipos_aceitos = _FILTRO_TIPO.get(tipo_sel)

                    for m in movs:
                        if tipos_aceitos and m.tipo.value not in tipos_aceitos:
                            continue
                        produto_lote = "—"
                        if m.lote and m.lote.produto:
                            produto_lote = (
                                f"{m.lote.produto.nome[:18]} | "
                                f"Lote {m.lote.num_lote}"
                            )
                        linhas.append({
                            "data_hora":  m.data_hora.strftime("%d/%m %H:%M:%S"),
                            "usuario":    m.usuario.nome[:14] if m.usuario else "Sistema",
                            "operacao":   _TIPO_LABEL.get(m.tipo.value, m.tipo.value),
                            "detalhe":    produto_lote,
                            "qtd":        str(m.quantidade),
                            "nf":         m.numero_nf or "—",
                            "obs":        (m.observacao or "")[:24],
                            "resultado":  "OK",
                            "cor_res":    COR_VERDE,
                        })

                # Alertas
                if tipo_sel in ("Todas as operações", "Alertas enviados"):
                    alertas = (
                        s.query(NotificacaoLog)
                        .options(joinedload(NotificacaoLog.lote).joinedload(Lote.produto))
                        .filter(NotificacaoLog.enviado_em.between(ini_dt, fim_dt))
                        .order_by(NotificacaoLog.enviado_em.desc())
                        .limit(200)
                        .all()
                    )
                    for a in alertas:
                        produto_lote = "—"
                        if a.lote and a.lote.produto:
                            produto_lote = (
                                f"{a.lote.produto.nome[:18]} | Lote {a.lote.num_lote}"
                            )
                        linhas.append({
                            "data_hora":  a.enviado_em.strftime("%d/%m %H:%M:%S"),
                            "usuario":    "Sistema",
                            "operacao":   f"Alerta {a.tipo_alerta.value}",
                            "detalhe":    produto_lote,
                            "qtd":        "—",
                            "nf":         "—",
                            "obs":        a.erro_msg[:24] if a.erro_msg else "",
                            "resultado":  "OK" if a.sucesso else "Falhou",
                            "cor_res":    COR_VERDE if a.sucesso else COR_VERM,
                        })

                # Jobs scheduler
                if tipo_sel in ("Todas as operações", "Jobs scheduler"):
                    jobs = (
                        s.query(JobLog)
                        .filter(JobLog.executado_em.between(ini_dt, fim_dt))
                        .order_by(JobLog.executado_em.desc())
                        .limit(100)
                        .all()
                    )
                    for j in jobs:
                        linhas.append({
                            "data_hora":  j.executado_em.strftime("%d/%m %H:%M:%S"),
                            "usuario":    "Scheduler",
                            "operacao":   j.job_nome[:20],
                            "detalhe":    (j.detalhe or "")[:30],
                            "qtd":        "—",
                            "nf":         "—",
                            "obs":        "",
                            "resultado":  "OK" if j.sucesso else "Falhou",
                            "cor_res":    COR_VERDE if j.sucesso else COR_VERM,
                        })

        except Exception as exc:
            logger.error("Erro ao carregar log: %s", exc)
            self._banner.erro(f"Erro ao carregar: {exc}")
            return

        # Ordenar por data desc
        linhas.sort(key=lambda x: x["data_hora"], reverse=True)
        self._linhas = linhas
        self._filtrar()

    def _filtrar(self):
        busca = self._entry_busca.get().lower()
        filtrados = [
            l for l in self._linhas
            if not busca
            or busca in l["usuario"].lower()
            or busca in l["detalhe"].lower()
            or busca in l["operacao"].lower()
        ]
        self._renderizar(filtrados)

    # ── Renderização ──────────────────────────────────────────────────────────

    def _renderizar(self, linhas: list[dict]):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not linhas:
            ctk.CTkLabel(self._scroll, text="Nenhum registro encontrado.",
                         text_color="#888780").pack(pady=24)
            self._lbl_rodape.configure(text="")
            return

        col_widths = [c[1] for c in _COLUNAS_MOV]

        for i, d in enumerate(linhas):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")
            row.grid_columnconfigure(3, weight=1)  # Detalhe é a coluna que expande

            valores = [
                d["data_hora"], d["usuario"], d["operacao"],
                d["detalhe"],   d["qtd"],     d["nf"], d["obs"],
            ]
            for col, (val, larg) in enumerate(zip(valores, col_widths)):
                ctk.CTkLabel(row, text=val, text_color="#3d3d3a",
                             font=ctk.CTkFont(size=11), width=larg,
                             anchor="w").grid(row=0, column=col, padx=4, pady=5, sticky="w")

            # Resultado (badge)
            fg_r = "#EAF3DE" if d["cor_res"] == COR_VERDE else "#FCEBEB"
            ctk.CTkLabel(row, text=d["resultado"],
                         fg_color=fg_r, text_color=d["cor_res"],
                         font=ctk.CTkFont(size=9, weight="bold"),
                         corner_radius=6, padx=6, pady=2, width=80).grid(
                row=0, column=7, padx=4, pady=5)

        self._lbl_rodape.configure(
            text=f"{len(linhas)} registro(s) exibidos — somente leitura.")
    