"""
gui.telas.t30_log_patrimonio.py
T-30 — Log de auditoria de Patrimônio (MOD-07) — perfil TI.
Exibe, em ordem cronológica, todos os eventos persistidos em
log_patrimonio: cadastro/transferência/baixa de bem, manutenção, ciclo de
vida de sessão de inventário e pareamento de dispositivo de coleta.
"""
import logging
from datetime import date, datetime, timedelta

import customtkinter as ctk

from fuso_horario import formatar
from gui.componentes.form_widgets import FeedbackBanner
from Modulo_07_patrimonio import PatrimonioService, PatrimonioError

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO,
)

_TIPOS_FILTRO = [
    "Todos os eventos",
    "Bens cadastrados",
    "Transferências",
    "Baixas",
    "Manutenções",
    "Sessões de inventário",
    "Pareamento de dispositivo",
]

_FILTRO_TIPO = {
    "Bens cadastrados":           {"bem_cadastrado"},
    "Transferências":             {"bem_transferido"},
    "Baixas":                     {"bem_baixado"},
    "Manutenções":                {"manutencao_registrada"},
    "Sessões de inventário":      {"sessao_aberta", "sessao_fechada", "sessao_cancelada"},
    "Pareamento de dispositivo":  {"dispositivo_pareado"},
}

_EVENTO_LABEL = {
    "bem_cadastrado":        "Bem cadastrado",
    "bem_transferido":       "Bem transferido",
    "bem_baixado":           "Bem baixado",
    "manutencao_registrada": "Manutenção registrada",
    "sessao_aberta":         "Sessão aberta",
    "sessao_fechada":        "Sessão fechada",
    "sessao_cancelada":      "Sessão cancelada",
    "dispositivo_pareado":   "Dispositivo pareado",
}

_COLUNAS = [
    ("Data/Hora", 130),
    ("Usuário",   130),
    ("Evento",    170),
]


class TelaLogPatrimonio(ctk.CTkFrame):
    """T-30 — Log de auditoria do Patrimônio (somente leitura)."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._servico = PatrimonioService()
        self._linhas: list[dict] = []
        self._pagina_atual = 0
        self._itens_por_pagina = 30
        self._lista_filtrada_atual = []
        self._carregando_pagina = False
        self._timer_scroll = None
        self._construir()
        self._carregar()
        self._monitorar_scroll()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text="Log de Patrimônio",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_PETROLEO_M).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(self._topbar, text="Atualizar", width=90, height=28,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._carregar).pack(side="right", padx=16, pady=8)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

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
            filt, values=_TIPOS_FILTRO, width=200, height=30, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#3d3d3a",
            command=lambda _v: self._filtrar(),
        )
        self._opt_tipo.set("Todos os eventos")
        self._opt_tipo.pack(side="left", padx=(0, 8))

        self._entry_busca = ctk.CTkEntry(filt, width=180, height=30, corner_radius=6,
                                          placeholder_text="Buscar usuário/descrição...")
        self._entry_busca.pack(side="left", padx=(0, 8))
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        ctk.CTkButton(filt, text="Filtrar", width=80, height=30,
                      fg_color=COR_PETROLEO_M, hover_color="#1a5276",
                      font=ctk.CTkFont(size=11),
                      command=self._carregar).pack(side="left")

        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(8, 0))
        hdr.grid_columnconfigure(3, weight=1)  # Descrição é a coluna que expande

        for col, (txt, larg) in enumerate(_COLUNAS):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=larg, anchor="w").grid(
                row=0, column=col, padx=4, pady=5, sticky="w")
        ctk.CTkLabel(hdr, text="DESCRIÇÃO", text_color="#888780",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     anchor="w").grid(row=0, column=3, padx=4, pady=5, sticky="w")

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

        try:
            ini_dt = datetime.combine(dt_ini, datetime.min.time())
            fim_dt = datetime.combine(dt_fim, datetime.max.time())
            # Sem tipo_evento aqui de propósito — o filtro de tipo é
            # client-side sobre self._linhas (ver _filtrar), evita
            # re-consultar o banco a cada troca no menu de tipo.
            eventos = self._servico.listar_log_periodo(self._usuario.id, ini_dt, fim_dt)
        except PatrimonioError as exc:
            logger.error("Erro ao carregar log de patrimônio: %s", exc)
            self._banner.erro(f"Erro ao carregar: {exc}")
            return
        except Exception as exc:
            logger.error("Erro ao carregar log de patrimônio: %s", exc)
            self._banner.erro(f"Erro ao carregar: {exc}")
            return

        linhas = [
            {
                "data_hora": e.criado_em,
                "_sort_dt":  e.criado_em,
                "usuario":   (e.usuario.nome[:16] if e.usuario else "—"),
                "evento":    _EVENTO_LABEL.get(e.tipo_evento.value, e.tipo_evento.value),
                "_tipo":     e.tipo_evento.value,
                "descricao": e.descricao or "",
            }
            for e in eventos
        ]
        linhas.sort(key=lambda x: x["_sort_dt"], reverse=True)
        self._linhas = linhas
        self._filtrar()

    def _filtrar(self):
        busca = self._entry_busca.get().lower()
        tipo_sel = self._opt_tipo.get()
        tipos_aceitos = _FILTRO_TIPO.get(tipo_sel)

        filtrados = [
            l for l in self._linhas
            if (not tipos_aceitos or l["_tipo"] in tipos_aceitos)
            and (not busca
                 or busca in l["usuario"].lower()
                 or busca in l["descricao"].lower()
                 or busca in l["evento"].lower())
        ]
        self._lista_filtrada_atual = filtrados
        self._pagina_atual = 0

        for w in self._scroll.winfo_children():
            w.destroy()

        self._renderizar_proxima_pagina()

    def _renderizar_proxima_pagina(self):
        self._carregando_pagina = True

        inicio = self._pagina_atual * self._itens_por_pagina
        fim = inicio + self._itens_por_pagina

        lote_linhas = self._lista_filtrada_atual[inicio:fim]
        if lote_linhas:
            self._renderizar(lote_linhas, limpar_tela=False)
            self._pagina_atual += 1
        elif self._pagina_atual == 0:
            # Primeira página sem nenhum resultado — chama _renderizar mesmo
            # vazia para exibir "Nenhum registro encontrado" (sem incrementar
            # _pagina_atual, então o monitor de scroll não insiste depois).
            self._renderizar([], limpar_tela=False)

        self.after(100, lambda: setattr(self, '_carregando_pagina', False))

    def _monitorar_scroll(self):
        inicio_proxima = self._pagina_atual * self._itens_por_pagina

        if not self._carregando_pagina and inicio_proxima < len(self._lista_filtrada_atual):
            try:
                _, bottom = self._scroll._parent_canvas.yview()
                if bottom >= 0.95:
                    self._renderizar_proxima_pagina()
            except Exception:
                pass

        self._timer_scroll = self.after(200, self._monitorar_scroll)

    # ── Renderização ──────────────────────────────────────────────────────────

    def _renderizar(self, linhas: list[dict], limpar_tela=True):
        if limpar_tela:
            for w in self._scroll.winfo_children():
                w.destroy()

        if not linhas and self._pagina_atual == 0:
            ctk.CTkLabel(self._scroll, text="Nenhum registro encontrado.",
                         text_color="#000000").pack(pady=24)
            self._lbl_rodape.configure(text="")
            return

        col_widths = [c[1] for c in _COLUNAS]

        if not hasattr(self, "_font_linha"):
            self._font_linha = ctk.CTkFont(size=11)

        for i, d in enumerate(linhas):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")
            row.grid_columnconfigure(3, weight=1)  # Descrição é a coluna que expande

            data_formatada = formatar(d["data_hora"], "%d/%m/%Y %H:%M:%S")
            valores = [data_formatada, d["usuario"], d["evento"]]
            for col, (val, larg) in enumerate(zip(valores, col_widths)):
                ctk.CTkLabel(row, text=val, text_color="#3d3d3a",
                             font=self._font_linha, width=larg,
                             anchor="w").grid(row=0, column=col, padx=4, pady=5, sticky="w")

            ctk.CTkLabel(row, text=d["descricao"], text_color="#3d3d3a",
                         font=self._font_linha, anchor="w", justify="left").grid(
                row=0, column=3, padx=4, pady=5, sticky="w")

        self._lbl_rodape.configure(
            text=f"{len(linhas)} registro(s) exibidos — somente leitura.")

        self._scroll.update_idletasks()

    def limpar_memoria(self):
        """Limpa os registros de log baixados do banco."""
        if hasattr(self, '_linhas') and self._linhas is not None:
            self._linhas.clear()
            self._linhas = None
