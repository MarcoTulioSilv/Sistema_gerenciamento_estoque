"""
gui · telas · t11_relatorios.py
Tela T-11 — Central de relatórios com Visualização, Envio e Filtros Dinâmicos (Sprint 4 / UI Refactor).
"""
import logging
import threading
from datetime import date, datetime
from tkinter import ttk
import customtkinter as ctk
from gui.componentes.form_widgets import FeedbackBanner
from Modulo_03_relatorios import RelatorioService

logger = logging.getLogger(__name__)

# Paleta de Cores do Projeto
COR_AZUL    = "#1F4E79"
COR_AZUL_M  = "#2E75B6"
COR_CINZA_E = "#F2F1ED"
COR_CINZA_B = "#E8E6DE"
COR_BRANCO  = "#FFFFFF"
COR_VERM    = "#A32D2D"
COR_VERDE   = "#1D9E75"


class TelaCentralRelatorios(ctk.CTkFrame):
    """Central de relatórios — alternância entre cartões de seleção e visualização em tabela com filtros."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._estilizar_treeview()
        self._construir()
        self._carregar_ultimo_envio()

    def _estilizar_treeview(self):
        """Aplica o estilo visual do sistema ao componente de tabela nativo do Tkinter."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Relatorio.Treeview",
                        background=COR_BRANCO,
                        foreground="#3d3d3a",
                        rowheight=26,
                        fieldbackground=COR_BRANCO,
                        bordercolor=COR_CINZA_B,
                        borderwidth=0,
                        font=("Arial", 10))
        style.configure("Relatorio.Treeview.Heading",
                        background=COR_AZUL,
                        foreground=COR_BRANCO,
                        relief="flat",
                        font=("Arial", 10, "bold"))
        style.map("Relatorio.Treeview",
                  background=[("selected", COR_AZUL_M)],
                  foreground=[("selected", COR_BRANCO)])

    # ── Construção Principal ──────────────────────────────────────────────────

    def _construir(self):
        # Topbar fixa
        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        
        self._lbl_titulo_topbar = ctk.CTkLabel(
            self._topbar, text="Central de relatórios",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COR_AZUL
        )
        self._lbl_titulo_topbar.pack(side="left", padx=16)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        # Container que vai alternar entre os Cartões e a Tabela
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True, padx=16, pady=12)

        # Vincula o clique no container principal para deselecionar a tabela
        self._container.bind("<Button-1>", lambda e: self._deselecionar_tabela())

        self._renderizar_cards()

    def _limpar_container(self):
        """Remove todos os widgets da tela atual para renderizar a próxima."""
        for widget in self._container.winfo_children():
            widget.destroy()

    def _deselecionar_tabela(self, event=None):
        """Remove a seleção da tabela ao clicar fora ou no espaço em branco."""
        if hasattr(self, "_tree") and self._tree:
            selecionados = self._tree.selection()
            if selecionados:
                self._tree.selection_remove(*selecionados)

    # ── Tela 1: Cartões de Seleção ────────────────────────────────────────────

    def _renderizar_cards(self):
        self._limpar_container()
        self._lbl_titulo_topbar.configure(text="Central de relatórios")

        scroll = ctk.CTkScrollableFrame(self._container, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)
        scroll.bind("<Button-1>", lambda e: self._deselecionar_tabela())

        # Card 1: Movimentação
        self._card_mov = _CardRelatorio(
            scroll, titulo="Relatório de movimentação",
            descricao="Entradas e saídas por período. Inclui produto, lote, NF, tipo e usuário.",
            cor_btn=COR_AZUL_M, texto_btn="Visualizar Relatório",
        )
        self._card_mov.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")

        per_frame = ctk.CTkFrame(self._card_mov, fg_color="transparent")
        per_frame.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkLabel(per_frame, text="De:", text_color="#5F5E5A", font=ctk.CTkFont(size=11)).pack(side="left")
        self._dt_ini = ctk.CTkEntry(per_frame, placeholder_text="DD/MM/AAAA", width=100, height=28, corner_radius=6)
        self._dt_ini.pack(side="left", padx=(4, 8))
        self._dt_ini.insert(0, _primeiro_do_mes())
        ctk.CTkLabel(per_frame, text="Até:", text_color="#5F5E5A", font=ctk.CTkFont(size=11)).pack(side="left")
        self._dt_fim = ctk.CTkEntry(per_frame, placeholder_text="DD/MM/AAAA", width=100, height=28, corner_radius=6)
        self._dt_fim.pack(side="left", padx=4)
        self._dt_fim.insert(0, date.today().strftime("%d/%m/%Y"))
        
        self._lbl_ult_mov = self._card_mov.label_ultimo_envio()
        self._card_mov.configurar_acao(self._iniciar_vis_movimentacao)

        # Card 2: Estoque atual
        self._card_est = _CardRelatorio(
            scroll, titulo="Relatório de estoque atual",
            descricao="Posição completa por produto e lote: quantidade, vencimento e situação.\nLotes vencidos destacados.",
            cor_btn=COR_AZUL_M, texto_btn="Visualizar Relatório",
        )
        self._card_est.grid(row=0, column=1, pady=(0, 8), sticky="nsew")
        self._lbl_ult_est = self._card_est.label_ultimo_envio()
        self._card_est.configurar_acao(
            lambda: self._abrir_tabela(
                "Estoque Atual",
                ["Produto", "Centro", "Lote", "NF", "Fab.", "Venc.", "Qtd Ini", "Qtd Atual", "Vlr Unit", "Vlr Total", "Situação"],
                RelatorioService.buscar_dados_estoque_atual,
                RelatorioService.gerar_e_enviar_estoque_atual,
                filtros_config=[("Centro:", 1), ("Situação:", 10)]
            )
        )

        # Card 3: A vencer
        self._card_venc = _CardRelatorio(
            scroll, titulo="Produtos próximos ao vencimento",
            descricao="Lotes com vencimento nos próximos 30 dias,\nordenados por data crescente.",
            cor_btn=COR_AZUL_M, texto_btn="Visualizar Relatório",
        )
        self._card_venc.grid(row=1, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        self._lbl_ult_venc = self._card_venc.label_ultimo_envio()
        self._card_venc.configurar_acao(
            lambda: self._abrir_tabela(
                "A Vencer (30 Dias)",
                ["Produto", "Centro", "Lote", "NF", "Vencimento", "Dias Restantes", "Qtd.", "Urgência"],
                RelatorioService.buscar_dados_a_vencer,
                RelatorioService.gerar_e_enviar_a_vencer,
                filtros_config=[("Centro:", 1), ("Urgência:", 7)]
            )
        )

        # Card 4: Lotes vencidos
        self._card_vencido = _CardRelatorio(
            scroll, titulo="Lotes vencidos em estoque",
            descricao="Lotes com data anterior a hoje e saldo > 0.\nTodos destacados — providencie o descarte.",
            cor_btn=COR_VERM, texto_btn="Visualizar Relatório", alerta=True,
        )
        self._card_vencido.grid(row=1, column=1, pady=(0, 8), sticky="nsew")
        self._lbl_ult_vencido = self._card_vencido.label_ultimo_envio()
        self._card_vencido.configurar_acao(
            lambda: self._abrir_tabela(
                "⚠ Lotes Vencidos em Estoque",
                ["Produto", "Centro", "Fornecedor", "Lote", "NF", "Vencimento", "Dias Vencido", "Qtd.", "Valor Estoque"],
                RelatorioService.buscar_dados_lotes_vencidos,
                RelatorioService.gerar_e_enviar_lotes_vencidos,
                filtros_config=[("Centro:", 1)]
            )
        )

        self._carregar_ultimo_envio()

    def _iniciar_vis_movimentacao(self):
        ini = _parse_date(self._dt_ini.get())
        fim = _parse_date(self._dt_fim.get())
        if not ini or not fim:
            self._banner.erro("Informe datas válidas no formato DD/MM/AAAA.")
            return
        if ini > fim:
            self._banner.erro("Data inicial não pode ser posterior à data final.")
            return
        
        self._abrir_tabela(
            f"Movimentação ({ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')})",
            ["Data/Hora", "Produto", "Lote", "NF", "Tipo", "Qtd.", "Usuário", "Observação"],
            lambda: RelatorioService.buscar_dados_movimentacao(ini, fim),
            lambda: RelatorioService.gerar_e_enviar_movimentacao(ini, fim),
            filtros_config=[("Tipo:", 4), ("Usuário:", 6)]
        )

    # ── Tela 2: Visualização da Tabela com Filtros ────────────────────────────

    def _abrir_tabela(self, titulo_relatorio, colunas, func_buscar_dados, func_enviar_email, filtros_config=None):
        self._limpar_container()
        self._lbl_titulo_topbar.configure(text=f"Central de relatórios → {titulo_relatorio}")

        # 1. Barra de Ferramentas Superior
        toolbar = ctk.CTkFrame(self._container, fg_color=COR_BRANCO, height=50, corner_radius=6)
        toolbar.pack(fill="x", pady=(0, 8))
        toolbar.bind("<Button-1>", lambda e: self._deselecionar_tabela())
        
        ctk.CTkButton(
            toolbar, text="⬅ Voltar aos Relatórios", width=160, height=32,
            fg_color="#5F5E5A", hover_color="#3d3d3a", command=self._renderizar_cards
        ).pack(side="left", padx=12, pady=9)

        btn_enviar = ctk.CTkButton(
            toolbar, text="✉️ Enviar por E-mail (XLSX)", width=180, height=32,
            fg_color=COR_VERDE, hover_color="#147556",
            command=lambda: self._disparar_envio_email(func_enviar_email)
        )
        btn_enviar.pack(side="right", padx=12, pady=9)

        btn_copiar = ctk.CTkButton(
            toolbar, text="📋 Copiar Dados (Excel)", width=160, height=32,
            fg_color=COR_AZUL_M, hover_color="#1a5276",
            command=lambda: self._copiar_para_area_de_transferencia()
        )
        btn_copiar.pack(side="right", padx=(0, 6), pady=9)

        # 2. Barra de Pesquisa e Filtros Dinâmicos
        frame_filtros = ctk.CTkFrame(self._container, fg_color=COR_BRANCO, corner_radius=6)
        frame_filtros.pack(fill="x", pady=(0, 10))
        frame_filtros.bind("<Button-1>", lambda e: self._deselecionar_tabela())

        self._entry_busca = ctk.CTkEntry(
            frame_filtros, placeholder_text="🔍 Pesquisar (Produto, Lote, NF, Data...)",
            height=32, corner_radius=6, fg_color=COR_CINZA_E, border_color=COR_CINZA_B, text_color="#3d3d3a"
        )
        self._entry_busca.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)
        self._entry_busca.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        self._combos_filtro = []
        if filtros_config:
            for label_texto, col_idx in filtros_config:
                lbl = ctk.CTkLabel(frame_filtros, text=label_texto, font=ctk.CTkFont(size=11, weight="bold"), text_color="#5F5E5A")
                lbl.pack(side="left", padx=(6, 2), pady=10)
                
                combo = ctk.CTkComboBox(
                    frame_filtros, values=["Todos"], width=135, height=32, corner_radius=6,
                    fg_color=COR_CINZA_E, border_color=COR_CINZA_B, text_color="#3d3d3a",
                    command=lambda val: self._aplicar_filtros()
                )
                combo.set("Todos")
                combo.pack(side="left", padx=(0, 8), pady=10)
                self._combos_filtro.append((combo, col_idx))

        btn_limpar = ctk.CTkButton(
            frame_filtros, text="✖ Limpar", width=80, height=32,
            fg_color="#F09595", hover_color=COR_VERM, text_color=COR_BRANCO,
            command=self._limpar_filtros_ui
        )
        btn_limpar.pack(side="right", padx=(4, 12), pady=10)

        # 3. Frame da Tabela e Scrollbars
        frame_tabela = ctk.CTkFrame(self._container, fg_color=COR_BRANCO, corner_radius=6)
        frame_tabela.pack(fill="both", expand=True)
        frame_tabela.grid_rowconfigure(0, weight=1)
        frame_tabela.grid_columnconfigure(0, weight=1)
        frame_tabela.bind("<Button-1>", lambda e: self._deselecionar_tabela())

        self._tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", style="Relatorio.Treeview")
        
        for col in colunas:
            self._tree.heading(col, text=col)
            if col in ("Produto", "Observação", "Fornecedor"):
                self._tree.column(col, width=240, minwidth=180, anchor="w", stretch=True)
            else:
                self._tree.column(col, width=115, minwidth=100, anchor="center", stretch=False)

        scroll_y = ttk.Scrollbar(frame_tabela, orient="vertical", command=self._tree.yview)
        scroll_x = ttk.Scrollbar(frame_tabela, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        # Label de Estado Vazio (Invisível por padrão)
        self._lbl_vazio = ctk.CTkLabel(
            frame_tabela, text="", font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#5F5E5A", justify="center"
        )
        self._lbl_vazio.bind("<Button-1>", lambda e: self._deselecionar_tabela())

        def _ao_clicar_no_tree(event):
            if not self._tree.identify_row(event.y):
                self._deselecionar_tabela()
        self._tree.bind("<Button-1>", _ao_clicar_no_tree)

        self._tree.bind("<Control-c>", lambda e: self._copiar_para_area_de_transferencia())
        self._tree.bind("<Control-C>", lambda e: self._copiar_para_area_de_transferencia())

        # Carrega os dados no banco
        self._banner.sucesso("Carregando dados do relatório...")
        
        def _carregar():
            try:
                dados = func_buscar_dados()
                self.after(0, lambda: self._configurar_dados_iniciais(dados, titulo_relatorio))
            except Exception as exc:
                logger.error("Erro ao buscar dados do relatório: %s", exc)
                self.after(0, lambda: self._banner.erro(f"Erro ao consultar banco: {exc}"))

        threading.Thread(target=_carregar, daemon=True).start()

    def _configurar_dados_iniciais(self, dados, titulo_relatorio):
        """Salva a lista original na memória, popula os comboboxes de filtro e desenha a tabela."""
        self._dados_originais = dados
        self._titulo_relatorio_atual = titulo_relatorio

        # Popula as opções únicas de cada Combobox dinamicamente
        for combo, col_idx in self._combos_filtro:
            unicos = sorted(list(set(
                str(linha[col_idx]).strip() for linha in dados 
                if linha[col_idx] and str(linha[col_idx]).strip() not in ("", "—")
            )))
            combo.configure(values=["Todos"] + unicos)
            combo.set("Todos")

        self._aplicar_filtros()

    def _limpar_filtros_ui(self):
        """Reseta o campo de busca e todos os comboboxes."""
        if hasattr(self, "_entry_busca"):
            self._entry_busca.delete(0, "end")
        for combo, _ in self._combos_filtro:
            combo.set("Todos")
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        """Filtra a lista em memória em tempo real e re-renderiza o Treeview."""
        if not hasattr(self, "_dados_originais") or self._dados_originais is None:
            return

        termo = self._entry_busca.get().lower().strip()
        dados_filtrados = []

        for linha in self._dados_originais:
            # 1. Filtro de Texto Geral (pesquisa em todas as colunas da linha)
            if termo and not any(termo in str(val).lower() for val in linha):
                continue
            
            # 2. Filtros Específicos de Combobox (Tipo, Usuário, Centro...)
            passou_combos = True
            for combo, col_idx in self._combos_filtro:
                val_combo = combo.get()
                if val_combo != "Todos":
                    if str(linha[col_idx]).strip().lower() != val_combo.lower():
                        passou_combos = False
                        break
            
            if passou_combos:
                dados_filtrados.append(linha)

        self._renderizar_treeview(dados_filtrados)

    def _renderizar_treeview(self, dados):
        """Desenha as linhas na tela e gerencia mensagens de estado vazio."""
        self._tree.delete(*self._tree.get_children())
        
        # Caso 1: O banco de dados retornou vazio desde o início
        if not self._dados_originais:
            msg_banner = "Nenhum registro encontrado para este relatório."
            msg_vazio  = "Nenhum registro encontrado."
            if any(p in self._titulo_relatorio_atual.lower() for p in ("vencer", "vencidos")):
                msg_banner = "✅ Excelente! Não há produtos que atendam a estas especificações no estoque."
                msg_vazio  = "✅ Excelente!\n\nNão há produtos que atendam a estas especificações no momento."
            
            self._banner.sucesso(msg_banner)
            self._tree.grid_remove()
            self._lbl_vazio.configure(text=msg_vazio)
            self._lbl_vazio.grid(row=0, column=0, sticky="nsew", pady=40)
            return

        # Caso 2: O banco tem dados, mas a pesquisa do usuário não encontrou nada
        if not dados:
            self._banner.sucesso("Nenhum registro encontrado para o filtro aplicado.")
            self._tree.grid_remove()
            self._lbl_vazio.configure(text="🔍 Nenhum resultado encontrado para a pesquisa.\n\nTente termos diferentes ou clique em Limpar.")
            self._lbl_vazio.grid(row=0, column=0, sticky="nsew", pady=40)
            return

        # Caso 3: Há dados filtrados para exibir
        self._lbl_vazio.grid_remove()
        self._tree.grid(row=0, column=0, sticky="nsew")

        for i, linha in enumerate(dados):
            tag = "par" if i % 2 == 0 else "impar"
            if any(str(val).upper() in ("VENCIDO", "CRÍTICO") for val in linha):
                tag = "critico"
            self._tree.insert("", "end", values=linha, tags=(tag,))

        self._tree.tag_configure("par", background=COR_BRANCO)
        self._tree.tag_configure("impar", background=COR_CINZA_E)
        self._tree.tag_configure("critico", background="#FCEBEB", foreground=COR_VERM)
        
        total_orig = len(self._dados_originais)
        total_filt = len(dados)
        if total_filt < total_orig:
            self._banner.sucesso(f"Exibindo {total_filt} de {total_orig} registros. Selecione linhas e use Ctrl+C para copiar.")
        else:
            self._banner.sucesso(f"Relatório carregado ({total_orig} registros). Selecione linhas e use Ctrl+C para copiar.")

    # ── Módulo de Cópia para Área de Transferência ────────────────────────────

    def _copiar_para_area_de_transferencia(self):
        selecionados = self._tree.selection()
        itens_para_copiar = selecionados if selecionados else self._tree.get_children()

        if not itens_para_copiar:
            self._banner.erro("Não há dados na tabela para copiar.")
            return

        linhas_texto = []
        cabecalhos = [self._tree.heading(c)["text"] for c in self._tree["columns"]]
        linhas_texto.append("\t".join(cabecalhos))

        for item_id in itens_para_copiar:
            valores = [str(val) for val in self._tree.item(item_id)["values"]]
            linhas_texto.append("\t".join(valores))

        texto_final = "\n".join(linhas_texto)
        self.clipboard_clear()
        self.clipboard_append(texto_final)
        
        qtd = len(itens_para_copiar)
        msg = f"{qtd} linha{'s' if qtd>1 else ''} copiada{'s' if qtd>1 else ''} para a área de transferência! Pronta para colar no Excel."
        self._banner.sucesso(msg)

    # ── Disparo de E-mail ─────────────────────────────────────────────────────

    def _disparar_envio_email(self, func_enviar_email):
        self._banner.sucesso("Gerando arquivo XLSX e enviando por e-mail... aguarde.")
        
        def _run():
            try:
                ret = func_enviar_email()
                if ret is None:
                    self.after(0, lambda: self._banner.sucesso("Envio cancelado: Nenhum dado para gerar relatório."))
                else:
                    self.after(0, lambda: self._banner.sucesso("✅ Relatório gerado em XLSX e enviado por e-mail com sucesso!"))
            except Exception as exc:
                logger.error("Erro ao enviar e-mail: %s", exc)
                self.after(0, lambda: self._banner.erro(f"Falha ao enviar e-mail: {exc}"))

        threading.Thread(target=_run, daemon=True).start()

    def _carregar_ultimo_envio(self):
        try:
            ags = {a.tipo_relatorio: a for a in RelatorioService.listar_agendamentos()}
            for tipo, lbl in [("movimentacao", self._lbl_ult_mov), ("estoque_atual", self._lbl_ult_est),
                              ("a_vencer", self._lbl_ult_venc), ("lotes_vencidos", self._lbl_ult_vencido)]:
                ag = ags.get(tipo)
                if ag and ag.ultimo_envio:
                    lbl.configure(text=f"Último envio: {ag.ultimo_envio.strftime('%d/%m/%Y %H:%M')}")
                else:
                    lbl.configure(text="Último envio: nunca")
        except Exception as exc:
            logger.warning("Erro ao carregar último envio: %s", exc)


# ── Componentes e Utilitários Auxiliares ─────────────────────────────────────

class _CardRelatorio(ctk.CTkFrame):
    def __init__(self, master, titulo, descricao, cor_btn, texto_btn, alerta=False, **kwargs):
        borda = "#F09595" if alerta else "#E8E6DE"
        super().__init__(master, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color=borda, **kwargs)
        cor_titulo = "#A32D2D" if alerta else "#1F4E79"
        ctk.CTkLabel(self, text=titulo, font=ctk.CTkFont(size=13, weight="bold"), text_color=cor_titulo, anchor="w", wraplength=340).pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(self, text=descricao, font=ctk.CTkFont(size=11), text_color="#5F5E5A", anchor="w", justify="left", wraplength=340).pack(fill="x", padx=14, pady=(4, 8))
        self._lbl_envio = ctk.CTkLabel(self, text="Último envio: —", font=ctk.CTkFont(size=10), text_color="#888780", anchor="w")
        self._lbl_envio.pack(fill="x", padx=14)
        self._btn = ctk.CTkButton(self, text=texto_btn, height=32, fg_color=cor_btn, hover_color="#1a5276", font=ctk.CTkFont(size=12))
        self._btn.pack(fill="x", padx=14, pady=12)

    def configurar_acao(self, fn):
        self._btn.configure(command=fn)

    def label_ultimo_envio(self) -> ctk.CTkLabel:
        return self._lbl_envio


def _parse_date(texto: str):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _primeiro_do_mes() -> str:
    hoje = date.today()
    return date(hoje.year, hoje.month, 1).strftime("%d/%m/%Y")