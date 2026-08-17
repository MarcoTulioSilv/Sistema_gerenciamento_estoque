"""
gui.telas.t23_bens_patrimoniais.py
Tela T-23 — Listagem de bens patrimoniais, filtros e seleção (MOD-07).
Padrão de scroll infinito de t10_posicao_estoque.py (CTkScrollableFrame).
"""
import logging
import customtkinter as ctk

from datetime import date

from gui.componentes.form_widgets import FeedbackBanner
from Modulo_07_patrimonio import PatrimonioService, FiltroBens, PatrimonioError
from Modulo_05_admin import ConfigService

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_PETROLEO_L, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM,
)

_SITUACAO_LABEL = {
    "ativo": "Ativo",
    "em_apuracao": "Em apuração",
    "baixado": "Baixado",
}
_SITUACAO_COR = {
    "Ativo":        ("#EAF3DE", "#27500A"),
    "Em apuração":  ("#FAEEDA", "#854F0B"),
    "Baixado":      ("#FCEBEB", "#A32D2D"),
}

_COLUNAS = [
    ("Tombo",              110),
    ("Descrição",          200),
    ("Marca / modelo",     140),
    ("Localização",        150),
    ("Situação",           100),
    ("Etiqueta",            80),
    ("Última manutenção",  130),
]

_FILTRO_SITUACAO = {
    "Ativos": ("ativo", True),
    "Em apuração": ("em_apuracao", False),
    "Baixados": ("baixado", False),
    "Todas": (None, False),
}

_FILTRO_MANUTENCAO = ["Todas", "Sem registro", "Há mais de N meses"]


class TelaBensPatrimoniais(ctk.CTkFrame):
    """T-23 — listagem de bens com filtros e seleção múltipla (RF-28)."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._servico = PatrimonioService()
        self._bens = []
        self._localizacoes = []
        self._selecionados: set[int] = set()
        self._timer_busca = None
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
        ctk.CTkLabel(self._topbar, text="Bens patrimoniais",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_PETROLEO).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(self._topbar, text="+ Cadastrar bem", width=140, height=28,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._on_navigate("novo_bem")).pack(side="right", padx=16, pady=8)

        # Filtros
        filt = ctk.CTkFrame(self, fg_color="transparent")
        filt.pack(fill="x", padx=16, pady=(10, 0))

        self._entry_busca = ctk.CTkEntry(
            filt, placeholder_text="Tombo ou descrição",
            height=32, width=240, corner_radius=6)
        self._entry_busca.pack(side="left")
        self._entry_busca.bind("<KeyRelease>", self._agendar_filtro)

        self._opt_localizacao = ctk.CTkOptionMenu(
            filt, values=["Todas as localizações"],
            width=190, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#161614",
            command=lambda _: self._filtrar())
        self._opt_localizacao.pack(side="left", padx=8)

        self._opt_situacao = ctk.CTkOptionMenu(
            filt, values=list(_FILTRO_SITUACAO.keys()),
            width=150, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#161614",
            command=lambda _: self._filtrar())
        self._opt_situacao.pack(side="left", padx=(0, 8))

        self._opt_manutencao = ctk.CTkOptionMenu(
            filt, values=_FILTRO_MANUTENCAO,
            width=170, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#161614",
            command=lambda _: self._filtrar())
        self._opt_manutencao.pack(side="left", padx=(0, 8))

        ctk.CTkButton(filt, text="limpar", width=70, height=32,
                      fg_color=COR_BRANCO, text_color="#161614",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=self._limpar_filtros).pack(side="left")

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

        # Barra de seleção (some quando não há seleção)
        self._barra_selecao = ctk.CTkFrame(self, fg_color=COR_PETROLEO_L, corner_radius=6)
        self._lbl_selecao = ctk.CTkLabel(self._barra_selecao, text="", text_color="#14504C",
                                         font=ctk.CTkFont(size=11, weight="bold"))
        self._lbl_selecao.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(self._barra_selecao, text="Imprimir na térmica (em breve)", width=190,
                      height=26, state="disabled", fg_color=COR_CINZA_B,
                      text_color="#AAAAAA", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self._barra_selecao, text="Gerar arquivo (em breve)", width=160,
                      height=26, state="disabled", fg_color=COR_CINZA_B,
                      text_color="#AAAAAA", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self._barra_selecao, text="Limpar seleção", width=110, height=26,
                      fg_color=COR_BRANCO, text_color="#161614",
                      border_width=1, border_color=COR_CINZA_B,
                      font=ctk.CTkFont(size=10),
                      command=self._limpar_selecao).pack(side="left", padx=(0, 12))

        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10, 0))
        hdr.grid_columnconfigure(len(_COLUNAS) + 1, weight=1)

        self._chk_todos = ctk.CTkCheckBox(hdr, text="", width=18, onvalue=True, offvalue=False,
                                          command=self._alternar_selecao_pagina)
        self._chk_todos.grid(row=0, column=0, padx=10, pady=5)

        for col, (txt, largura) in enumerate(_COLUNAS, start=1):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=9, weight="bold"),
                         width=largura, anchor="w"
                         ).grid(row=0, column=col, padx=6, pady=5, sticky="w")
        ctk.CTkLabel(hdr, text="", width=70).grid(row=0, column=len(_COLUNAS) + 1, padx=6, pady=5)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=COR_BRANCO,
            border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._lbl_rodape = ctk.CTkLabel(
            self, text="", text_color="#888780", font=ctk.CTkFont(size=10))
        self._lbl_rodape.pack(anchor="w", padx=18, pady=(0, 8))

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        try:
            self._meses_alerta = int(ConfigService.get("manutencao_alerta_meses") or "12")
        except (ValueError, TypeError):
            self._meses_alerta = 12

        try:
            self._localizacoes = self._servico.listar_localizacoes(self._usuario.id)
            labels = ["Todas as localizações"] + [loc.nome_completo for loc in self._localizacoes]
            self._opt_localizacao.configure(values=labels)

            self._bens = self._servico.listar_bens_com_manutencao(
                self._usuario.id, FiltroBens(apenas_ativos=False))
        except PatrimonioError as exc:
            logger.error("Erro ao carregar bens patrimoniais: %s", exc)
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao carregar bens patrimoniais: %s", exc)
            self._banner.erro(f"Erro ao carregar bens: {exc}")
            return

        self._opt_situacao.set("Ativos")
        self._filtrar()

    def _filtrar(self):
        busca = self._entry_busca.get().lower().strip()
        loc_label = self._opt_localizacao.get()
        situacao_opt = self._opt_situacao.get()
        situacao_alvo, _ = _FILTRO_SITUACAO.get(situacao_opt, (None, False))
        manutencao_opt = self._opt_manutencao.get()
        hoje = date.today()

        filtrados = []
        for bem, ultima_manutencao in self._bens:
            if busca and busca not in bem.tombo.lower() and busca not in bem.descricao.lower():
                continue
            if loc_label != "Todas as localizações" and (not bem.localizacao or bem.localizacao.nome_completo != loc_label):
                continue
            if situacao_alvo and bem.situacao.value != situacao_alvo:
                continue
            if manutencao_opt == "Sem registro" and ultima_manutencao is not None:
                continue
            if manutencao_opt == "Há mais de N meses":
                if ultima_manutencao is not None:
                    meses_desde = (hoje.year - ultima_manutencao.year) * 12 + (hoje.month - ultima_manutencao.month)
                    if meses_desde < self._meses_alerta:
                        continue
            filtrados.append((bem, ultima_manutencao))

        self._lista_filtrada_atual = filtrados
        self._pagina_atual = 0

        for w in self._scroll.winfo_children():
            w.destroy()

        self._renderizar_proxima_pagina()

    def _renderizar_proxima_pagina(self):
        self._carregando_pagina = True

        inicio = self._pagina_atual * self._itens_por_pagina
        fim = inicio + self._itens_por_pagina
        bens_pagina = self._lista_filtrada_atual[inicio:fim]
        self._renderizar(bens_pagina, limpar_tela=False)

        self._pagina_atual += 1
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

    def _limpar_filtros(self):
        self._entry_busca.delete(0, "end")
        self._opt_localizacao.set("Todas as localizações")
        self._opt_situacao.set("Ativos")
        self._opt_manutencao.set("Todas")
        self._filtrar()

    def _agendar_filtro(self, event=None):
        if self._timer_busca is not None:
            self.after_cancel(self._timer_busca)
        self._timer_busca = self.after(400, self._filtrar)

    # ── Seleção ───────────────────────────────────────────────────────────────

    def _alternar_bem(self, bem_id: int, marcado: bool):
        if marcado:
            self._selecionados.add(bem_id)
        else:
            self._selecionados.discard(bem_id)
        self._atualizar_barra_selecao()

    def _alternar_selecao_pagina(self):
        marcar = bool(self._chk_todos.get())
        visiveis = self._lista_filtrada_atual[:self._pagina_atual * self._itens_por_pagina]
        for bem, _ in visiveis:
            if marcar:
                self._selecionados.add(bem.id)
            else:
                self._selecionados.discard(bem.id)
        self._filtrar_sem_resetar_pagina()

    def _filtrar_sem_resetar_pagina(self):
        pagina_atual = self._pagina_atual
        for w in self._scroll.winfo_children():
            w.destroy()
        self._pagina_atual = 0
        while self._pagina_atual < pagina_atual:
            self._renderizar_proxima_pagina()

    def _limpar_selecao(self):
        self._selecionados.clear()
        self._atualizar_barra_selecao()
        self._filtrar_sem_resetar_pagina()

    def _atualizar_barra_selecao(self):
        n = len(self._selecionados)
        if n > 0:
            self._lbl_selecao.configure(text=f"{n} bem(ns) selecionado(s)")
            if not self._barra_selecao.winfo_ismapped():
                self._barra_selecao.pack(fill="x", padx=16, pady=(0, 10), after=self._banner)
        else:
            self._barra_selecao.pack_forget()
        self._lbl_rodape.configure(
            text=self._lbl_rodape.cget("text").split(" · ")[0] +
                 (f" · {n} selecionado(s)" if n else ""))

    # ── Renderização ──────────────────────────────────────────────────────────

    def _renderizar(self, bens, limpar_tela=True):
        if limpar_tela:
            for w in self._scroll.winfo_children():
                w.destroy()

        if not bens and self._pagina_atual == 0:
            ctk.CTkLabel(self._scroll, text="Nenhum bem encontrado.",
                        text_color=COR_VERM,
                        font=ctk.CTkFont(size=12)).pack(pady=24)
            self._lbl_rodape.configure(text="")
            return

        for i, (bem, ultima_manutencao) in enumerate(bens):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")
            row.grid_columnconfigure(len(_COLUNAS) + 1, weight=1)

            var = ctk.BooleanVar(value=bem.id in self._selecionados)
            ctk.CTkCheckBox(row, text="", width=18, variable=var,
                            command=lambda b=bem.id, v=var: self._alternar_bem(b, v.get())
                            ).grid(row=0, column=0, padx=10, pady=4)

            situacao_label = _SITUACAO_LABEL.get(bem.situacao.value, bem.situacao.value)
            valores = [
                bem.tombo,
                bem.descricao[:34],
                bem.marca_modelo or "—",
                bem.localizacao.nome_completo if bem.localizacao else "—",
            ]
            for col, val in enumerate(valores, start=1):
                largura = _COLUNAS[col - 1][1]
                cor = COR_PETROLEO if col == 1 else "#3d3d3a"
                fonte = ctk.CTkFont(size=11, weight="bold", family="Consolas") if col == 1 else ctk.CTkFont(size=11)
                ctk.CTkLabel(row, text=val, text_color=cor, font=fonte,
                             width=largura, anchor="w"
                             ).grid(row=0, column=col, padx=6, pady=6, sticky="w")

            fg_s, tc_s = _SITUACAO_COR.get(situacao_label, ("#F1EFE8", "#5F5E5A"))
            ctk.CTkLabel(row, text=situacao_label, fg_color=fg_s, text_color=tc_s,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         corner_radius=6, padx=6, pady=2, width=_COLUNAS[4][1], height=24
                         ).grid(row=0, column=5, padx=6, pady=6)

            ctk.CTkLabel(row, text="—", text_color="#888780",
                         font=ctk.CTkFont(size=10), width=_COLUNAS[5][1], anchor="center"
                         ).grid(row=0, column=6, padx=6, pady=6)

            if ultima_manutencao:
                txt_manut, cor_manut = ultima_manutencao.strftime("%d/%m/%Y"), "#3d3d3a"
            else:
                txt_manut, cor_manut = "Nunca", "#854F0B"
            ctk.CTkLabel(row, text=txt_manut, text_color=cor_manut,
                         font=ctk.CTkFont(size=11), width=_COLUNAS[6][1], anchor="w"
                         ).grid(row=0, column=7, padx=6, pady=6, sticky="w")

            ctk.CTkButton(
                row, text="Abrir", width=64, height=26,
                fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                border_width=1, border_color=COR_CINZA_B,
                hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                command=lambda b=bem.id: self._on_navigate("movimentar_bem", extra=b)
            ).grid(row=0, column=len(_COLUNAS) + 1, padx=6, pady=4, sticky="e")

        total = len(self._lista_filtrada_atual)
        mostrados = min(self._pagina_atual * self._itens_por_pagina, total)
        self._lbl_rodape.configure(
            text=f"{mostrados} de {total} bem(ns)" +
                 (f" · {len(self._selecionados)} selecionado(s)" if self._selecionados else ""))

    def limpar_memoria(self):
        """Chamado pelo app.py ao sair da tela para esvaziar a RAM."""
        if self._bens is not None:
            self._bens.clear()
            self._bens = None
        if self._timer_scroll is not None:
            self.after_cancel(self._timer_scroll)
            self._timer_scroll = None
        if self._timer_busca is not None:
            self.after_cancel(self._timer_busca)
            self._timer_busca = None
