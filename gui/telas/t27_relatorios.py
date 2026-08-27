"""
gui.telas.t27_relatorios.py
Tela T-27 — Relatórios de patrimônio (MOD-07, RF-35).

Um card, seleção por rádio entre 5 tipos de relatório, filtros que mudam
conforme o tipo, três ações: Visualizar (painel flutuante com prévia em
tabela), Enviar por e-mail e Gerar XLSX. Restrita a admin/ti (RF-35 —
Gestora + TI, técnico sem acesso).
"""
import logging
import shutil
from datetime import date, datetime, timedelta
from tkinter import filedialog

import customtkinter as ctk

from fuso_horario import formatar

from gui.componentes.form_widgets import FeedbackBanner
from gui.componentes.tabela_scroll import TabelaScroll
from Modulo_07_patrimonio import PatrimonioService, InventarioService, PatrimonioError

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_PETROLEO_L, COR_CINZA_E, COR_CINZA_B, COR_BRANCO, COR_VERM,
)

_TIPOS = [
    ("bens_ativos", "Bens ativos", "Acervo agrupado por setor e sala."),
    ("divergencias", "Divergências de sessão", "Resultado completo de uma campanha."),
    ("historico_movimentacao", "Histórico de movimentação", "Trajetória dos bens em um período."),
    ("bens_baixados", "Bens descartados/inativados", "Baixas registradas num período."),
    ("manutencoes", "Manutenções", "Serviços realizados nos bens."),
]

_STATUS_SESSAO_LABEL = {"aberto": "Aberta", "finalizado": "Finalizada", "cancelado": "Cancelada"}


class TelaRelatoriosPatrimonio(ctk.CTkFrame):
    """T-27 — geração/envio de relatórios de patrimônio (RF-35)."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._servico = PatrimonioService()
        self._inventario_servico = InventarioService()
        self._tipo_atual = _TIPOS[0][0]
        self._sessoes = []
        self._localizacoes = []
        self._painel_visualizacao = None
        self._construir()
        self._carregar_opcoes()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Relatórios de patrimônio",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_PETROLEO).pack(side="left", padx=16, pady=10)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

        card = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=8,
                            border_width=1, border_color=COR_CINZA_B)
        card.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(card, text="Tipo de relatório", font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(14, 4))

        grade_tipos = ctk.CTkFrame(card, fg_color="transparent")
        grade_tipos.pack(fill="x", padx=16)
        self._var_tipo = ctk.StringVar(value=self._tipo_atual)
        for i, (chave, titulo, descricao) in enumerate(_TIPOS):
            wrap = ctk.CTkFrame(grade_tipos, fg_color=COR_CINZA_E, corner_radius=6)
            wrap.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="nsew")
            grade_tipos.grid_columnconfigure(i % 3, weight=1)
            ctk.CTkRadioButton(wrap, text=titulo, variable=self._var_tipo, value=chave,
                               font=ctk.CTkFont(size=12, weight="bold"),
                               command=self._ao_selecionar_tipo).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(wrap, text=descricao, text_color="#888780", font=ctk.CTkFont(size=10),
                        wraplength=220, justify="left", anchor="w"
                        ).pack(anchor="w", padx=30, pady=(0, 8))

        ctk.CTkLabel(card, text="Filtros", font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COR_PETROLEO).pack(anchor="w", padx=16, pady=(12, 4))
        self._area_filtros = ctk.CTkFrame(card, fg_color="transparent")
        self._area_filtros.pack(fill="x", padx=16, pady=(0, 8))

        rodape = ctk.CTkFrame(card, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(4, 16))
        ctk.CTkButton(rodape, text="Visualizar", width=120, height=32,
                     fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     command=self._visualizar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(rodape, text="Enviar por e-mail", width=150, height=32,
                     fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     command=self._enviar_email).pack(side="left", padx=(0, 8))
        ctk.CTkButton(rodape, text="Gerar XLSX", width=130, height=32,
                     fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                     command=self._gerar_xlsx).pack(side="left")

        self._montar_filtros()

    def _carregar_opcoes(self):
        try:
            self._localizacoes = self._servico.listar_localizacoes(self._usuario.id)
            self._sessoes = self._inventario_servico.listar_sessoes()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        self._montar_filtros()

    # ── Filtros dinâmicos ────────────────────────────────────────────────────

    def _ao_selecionar_tipo(self):
        self._tipo_atual = self._var_tipo.get()
        self._montar_filtros()

    def _montar_filtros(self):
        for w in self._area_filtros.winfo_children():
            w.destroy()

        labels_loc = ["Todas as localizações"] + [loc.nome_completo for loc in self._localizacoes]

        if self._tipo_atual == "bens_ativos":
            ctk.CTkLabel(self._area_filtros, text="Localização:").pack(side="left", padx=(0, 6))
            self._opt_localizacao = ctk.CTkOptionMenu(
                self._area_filtros, values=labels_loc, width=220, height=32,
                fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#161614")
            self._opt_localizacao.pack(side="left")

        elif self._tipo_atual == "divergencias":
            ctk.CTkLabel(self._area_filtros, text="Sessão:").pack(side="left", padx=(0, 6))
            rotulos = [self._rotulo_sessao(s) for s in self._sessoes] or ["Nenhuma sessão encontrada"]
            self._opt_sessao = ctk.CTkOptionMenu(
                self._area_filtros, values=rotulos, width=380, height=32,
                fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#161614")
            self._opt_sessao.pack(side="left")

        elif self._tipo_atual == "historico_movimentacao":
            ctk.CTkLabel(self._area_filtros, text="Localização:").pack(side="left", padx=(0, 6))
            self._opt_localizacao = ctk.CTkOptionMenu(
                self._area_filtros, values=labels_loc, width=200, height=32,
                fg_color=COR_BRANCO, button_color=COR_PETROLEO_M, text_color="#161614")
            self._opt_localizacao.pack(side="left", padx=(0, 16))
            self._campo_data_ini, self._campo_data_fim = self._adicionar_campos_periodo(
                padrao_ini=date.today() - timedelta(days=30))

        elif self._tipo_atual == "bens_baixados":
            self._campo_data_ini, self._campo_data_fim = self._adicionar_campos_periodo(
                padrao_ini=date.today() - timedelta(days=90))

        elif self._tipo_atual == "manutencoes":
            ctk.CTkLabel(self._area_filtros, text="(opcional — vazio mostra tudo)",
                        text_color="#888780", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 8))
            self._campo_data_ini, self._campo_data_fim = self._adicionar_campos_periodo(padrao_ini=None)

    def _adicionar_campos_periodo(self, padrao_ini: date | None):
        ctk.CTkLabel(self._area_filtros, text="De:").pack(side="left", padx=(0, 6))
        campo_ini = ctk.CTkEntry(self._area_filtros, placeholder_text="dd/mm/aaaa", width=110, height=32)
        if padrao_ini:
            campo_ini.insert(0, padrao_ini.strftime("%d/%m/%Y"))
        campo_ini.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(self._area_filtros, text="Até:").pack(side="left", padx=(0, 6))
        campo_fim = ctk.CTkEntry(self._area_filtros, placeholder_text="dd/mm/aaaa", width=110, height=32)
        campo_fim.insert(0, date.today().strftime("%d/%m/%Y"))
        campo_fim.pack(side="left")
        return campo_ini, campo_fim

    def _rotulo_sessao(self, sessao) -> str:
        status = _STATUS_SESSAO_LABEL.get(sessao.status.value, sessao.status.value)
        return f"#{sessao.id} — {sessao.descricao} ({status}, {formatar(sessao.aberto_em, '%d/%m/%Y')})"

    def _loc_id_por_label(self, label: str):
        for loc in self._localizacoes:
            if loc.nome_completo == label:
                return loc.id
        return None

    def _sessao_id_selecionada(self):
        rotulo = self._opt_sessao.get()
        for s in self._sessoes:
            if self._rotulo_sessao(s) == rotulo:
                return s.id
        return None

    def _parse_data(self, entry: ctk.CTkEntry, obrigatoria: bool = True):
        texto = entry.get().strip()
        if not texto:
            if obrigatoria:
                raise ValueError("Informe as duas datas do período.")
            return None
        try:
            return datetime.strptime(texto, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError(f"Data inválida: '{texto}' — use dd/mm/aaaa.")

    # ── Ações ────────────────────────────────────────────────────────────────

    def _dados_e_colunas_atuais(self):
        """
        Devolve (colunas, linhas_texto, gerar_fn, enviar_fn) pro tipo
        selecionado — gerar_fn/enviar_fn não recebem argumento (já vêm
        fechados sobre os filtros atuais), pra Visualizar/Gerar/Enviar
        chamarem do mesmo jeito não importa o tipo.
        """
        if self._tipo_atual == "bens_ativos":
            loc_id = self._loc_id_por_label(self._opt_localizacao.get())
            bens = self._servico.listar_bens_ativos(self._usuario.id, loc_id)
            colunas = [("Tombo", 90), ("Descrição", 260), ("Marca/modelo", 160),
                      ("Localização", 200), ("Nota fiscal", 120)]
            linhas = [[b.tombo, b.descricao, b.marca_modelo or "—",
                      b.localizacao.nome_completo if b.localizacao else "—", b.nota_fiscal or "—"]
                     for b in bens]
            gerar = lambda: self._servico.relatorio_bens_ativos(self._usuario.id, loc_id)
            enviar = lambda: self._servico.enviar_relatorio_bens_ativos(self._usuario.id, loc_id)
            return colunas, linhas, gerar, enviar

        if self._tipo_atual == "divergencias":
            sessao_id = self._sessao_id_selecionada()
            if not sessao_id:
                raise ValueError("Selecione uma sessão.")
            itens = self._inventario_servico.listar_itens(sessao_id, "divergente_local")
            colunas = [("Tombo", 90), ("Descrição", 260), ("Esperado", 200), ("Encontrado", 200)]
            linhas = [[i.bem.tombo, i.bem.descricao,
                      i.localizacao_esperada.nome_completo if i.localizacao_esperada else "—",
                      i.localizacao_encontrada.nome_completo if i.localizacao_encontrada else "—"]
                     for i in itens]
            gerar = lambda: self._inventario_servico.gerar_relatorio(sessao_id, self._usuario.id)
            enviar = lambda: self._inventario_servico.enviar_relatorio(sessao_id, self._usuario.id)
            return colunas, linhas, gerar, enviar

        if self._tipo_atual == "historico_movimentacao":
            loc_id = self._loc_id_por_label(self._opt_localizacao.get())
            data_ini = self._parse_data(self._campo_data_ini)
            data_fim = self._parse_data(self._campo_data_fim)
            dt_ini = datetime.combine(data_ini, datetime.min.time())
            dt_fim = datetime.combine(data_fim, datetime.max.time())
            movs = self._servico.listar_historico_movimentacao(self._usuario.id, dt_ini, dt_fim, loc_id)
            colunas = [("Data/Hora", 130), ("Tombo", 90), ("Descrição", 220), ("Tipo", 140),
                      ("Origem", 180), ("Destino", 180), ("Motivo", 200), ("Usuário", 140)]
            _tipo_label = {"cadastro": "Cadastro", "transferencia": "Transferência",
                          "ajuste_inventario": "Ajuste de inventário", "baixa": "Baixa"}
            linhas = [[formatar(m.data_hora, "%d/%m/%Y %H:%M"), m.bem.tombo, m.bem.descricao,
                      _tipo_label.get(m.tipo.value, m.tipo.value),
                      m.localizacao_origem.nome_completo if m.localizacao_origem else "—",
                      m.localizacao_destino.nome_completo if m.localizacao_destino else "—",
                      m.motivo or "—", m.usuario.nome]
                     for m in movs]
            gerar = lambda: self._servico.relatorio_historico_movimentacao(self._usuario.id, dt_ini, dt_fim, loc_id)
            enviar = lambda: self._servico.enviar_historico_movimentacao(self._usuario.id, dt_ini, dt_fim, loc_id)
            return colunas, linhas, gerar, enviar

        if self._tipo_atual == "bens_baixados":
            data_ini = self._parse_data(self._campo_data_ini)
            data_fim = self._parse_data(self._campo_data_fim)
            baixas = self._servico.listar_bens_baixados(self._usuario.id, data_ini, data_fim)
            colunas = [("Tombo", 90), ("Descrição", 220), ("Motivo", 140), ("Data baixa", 100),
                      ("Documento", 160), ("MTR", 120), ("Laudo", 120), ("Usuário", 140)]
            _motivo_label = {"descarte": "Descarte", "doacao": "Doação", "venda": "Venda",
                             "extravio": "Extravio", "obsolescencia": "Obsolescência", "sinistro": "Sinistro"}
            linhas = [[b.bem.tombo, b.bem.descricao, _motivo_label.get(b.motivo.value, b.motivo.value),
                      b.data_baixa.strftime("%d/%m/%Y"), b.documento or "—",
                      b.numero_mtr or "—", b.numero_laudo or "—", b.usuario.nome]
                     for b in baixas]
            gerar = lambda: self._servico.relatorio_bens_baixados(self._usuario.id, data_ini, data_fim)
            enviar = lambda: self._servico.enviar_relatorio_bens_baixados(self._usuario.id, data_ini, data_fim)
            return colunas, linhas, gerar, enviar

        # manutencoes
        data_ini = self._parse_data(self._campo_data_ini, obrigatoria=False)
        data_fim = self._parse_data(self._campo_data_fim, obrigatoria=False)
        manutencoes = self._servico.listar_manutencoes(self._usuario.id, data_ini, data_fim)
        colunas = [("Tombo", 90), ("Descrição", 220), ("Data manutenção", 130),
                  ("Serviço realizado", 320), ("Registrado por", 140)]
        linhas = [[m.bem.tombo, m.bem.descricao, m.data_manutencao.strftime("%d/%m/%Y"),
                  m.descricao, m.usuario.nome]
                 for m in manutencoes]
        gerar = lambda: self._servico.relatorio_manutencoes(self._usuario.id, data_ini, data_fim)
        enviar = lambda: self._servico.enviar_relatorio_manutencoes(self._usuario.id, data_ini, data_fim)
        return colunas, linhas, gerar, enviar

    def _visualizar(self):
        try:
            colunas, linhas, gerar, enviar = self._dados_e_colunas_atuais()
        except (ValueError, PatrimonioError) as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao carregar dados do relatório: %s", exc)
            self._banner.erro(f"Erro ao carregar dados: {exc}")
            return

        if self._painel_visualizacao:
            self._painel_visualizacao.destroy()
        titulo = dict((c, t) for c, t, _ in _TIPOS)[self._tipo_atual]
        self._painel_visualizacao = _PainelVisualizacaoRelatorio(
            self, titulo=titulo, colunas=colunas, linhas=linhas,
            on_gerar=lambda: self._concluir_gerar(gerar),
            on_enviar=lambda: self._concluir_enviar(enviar),
            on_fechar=self._fechar_painel_visualizacao,
        )
        self._painel_visualizacao.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.75, relheight=0.75)

    def _fechar_painel_visualizacao(self):
        if self._painel_visualizacao:
            self._painel_visualizacao.destroy()
            self._painel_visualizacao = None

    def _gerar_xlsx(self):
        try:
            _, _, gerar, _ = self._dados_e_colunas_atuais()
        except (ValueError, PatrimonioError) as exc:
            self._banner.erro(str(exc))
            return
        self._concluir_gerar(gerar)

    def _enviar_email(self):
        try:
            _, _, _, enviar = self._dados_e_colunas_atuais()
        except (ValueError, PatrimonioError) as exc:
            self._banner.erro(str(exc))
            return
        self._concluir_enviar(enviar)

    def _concluir_gerar(self, gerar_fn):
        try:
            caminho = gerar_fn()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao gerar relatório: %s", exc)
            self._banner.erro(f"Erro ao gerar relatório: {exc}")
            return

        destino = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile="relatorio_patrimonio.xlsx")
        if destino:
            try:
                shutil.copy(caminho, destino)
                self._banner.sucesso(f"Relatório salvo em {destino}.")
            except OSError as exc:
                self._banner.erro(f"Erro ao salvar arquivo: {exc}")
        else:
            self._banner.sucesso(f"Relatório gerado — arquivo temporário em {caminho}.")

    def _concluir_enviar(self, enviar_fn):
        try:
            enviar_fn()
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao enviar relatório por e-mail: %s", exc)
            self._banner.erro(f"Erro ao enviar por e-mail: {exc}")
            return
        self._banner.sucesso("Relatório enviado por e-mail.")

    def limpar_memoria(self):
        """Chamado pelo app.py ao sair da tela para esvaziar a RAM."""
        self._fechar_painel_visualizacao()
        self._sessoes = None
        self._localizacoes = None


class _PainelVisualizacaoRelatorio(ctk.CTkFrame):
    """
    Painel flutuante de pré-visualização — mesma tabela que viraria XLSX,
    renderizada via TabelaScroll (cabeçalho+linhas na mesma grade, scroll
    vertical e horizontal reais). Tem seus próprios botões Enviar/Gerar,
    chamando as mesmas funções de serviço da tela principal.
    """

    def __init__(self, master, titulo, colunas, linhas, on_gerar, on_enviar, on_fechar):
        super().__init__(master, fg_color=COR_BRANCO, corner_radius=10,
                         border_width=1, border_color=COR_CINZA_B)
        self._on_gerar = on_gerar
        self._on_enviar = on_enviar
        self._on_fechar = on_fechar

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(topo, text=f"Pré-visualização — {titulo}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COR_PETROLEO).pack(side="left")
        ctk.CTkButton(topo, text="✕", width=28, height=28, fg_color="transparent",
                     text_color="#888780", hover_color=COR_CINZA_E,
                     command=self._on_fechar).pack(side="right")

        ctk.CTkLabel(self, text=f"{len(linhas)} registro(s)",
                    text_color="#888780", font=ctk.CTkFont(size=10)
                    ).pack(anchor="w", padx=16, pady=(0, 6))

        tabela = TabelaScroll(self, fg_color_grade=COR_BRANCO,
                              border_width=1, border_color=COR_CINZA_B, corner_radius=0)
        tabela.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        grade = tabela.grade
        for col, (_, largura) in enumerate(colunas):
            grade.grid_columnconfigure(col, minsize=largura)
        for col, (nome, _) in enumerate(colunas):
            ctk.CTkLabel(grade, text=nome.upper(), text_color="#888780", corner_radius=6,
                        font=ctk.CTkFont(size=9, weight="bold"), fg_color=COR_PETROLEO_L,
                        anchor="center").grid(row=0, column=col, padx=8, pady=6, sticky="nsew")
        if not linhas:
            ctk.CTkLabel(grade, text="Nenhum registro encontrado.", text_color=COR_VERM,
                        font=ctk.CTkFont(size=12)
                        ).grid(row=1, column=0, columnspan=len(colunas), pady=20)
        for i, linha in enumerate(linhas, 1):
            bg = COR_BRANCO if i % 2 == 1 else COR_CINZA_E
            for col, val in enumerate(linha):
                ctk.CTkLabel(grade, text=str(val), text_color="#3d3d3a", fg_color=bg, corner_radius= 6,
                            font=ctk.CTkFont(size=11), anchor="w"
                            ).grid(row=i, column=col, padx=8, pady=4, sticky="nsew")

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(rodape, text="Enviar por e-mail", width=150, height=32,
                     fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                     border_width=1, border_color=COR_CINZA_B, hover_color=COR_CINZA_E,
                     command=self._on_enviar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(rodape, text="Gerar XLSX", width=130, height=32,
                     fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                     command=self._on_gerar).pack(side="left")
