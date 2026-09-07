"""
gui.telas.t24_cadastro_bem.py
Tela T-24 — Cadastro e edição de bem patrimonial (MOD-07, RF-25/RF-26).
"""
import logging
import customtkinter as ctk

from gui.componentes.form_widgets import Campo, SecaoFormulario, FeedbackBanner
from gui.componentes.seletor_impressora import SeletorImpressora
from Modulo_07_patrimonio import PatrimonioService, DadosBem, PatrimonioError, SaidaEtiqueta

logger = logging.getLogger(__name__)

from gui.componentes.tema import (
    COR_PETROLEO, COR_PETROLEO_M, COR_CINZA_E, COR_CINZA_B, COR_BRANCO,
)


class TelaCadastroBem(ctk.CTkFrame):
    """Cadastro (RF-25/RF-26) e edição de bem patrimonial. Não move o bem — mudança de localização é T-25."""

    def __init__(self, master, usuario, on_navigate, bem_id: int = None):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario = usuario
        self._on_navigate = on_navigate
        self._bem_id = bem_id
        self._servico = PatrimonioService()
        self._localizacoes = []
        self._painel_impressora = None
        self._bem_id_para_imprimir = None
        self._construir()
        if self._bem_id:
            self._preencher_bem(self._bem_id)
        else:
            self._carregar_preview_tombo()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        titulo = "Editar bem" if self._bem_id else "Cadastrar bem"

        self._topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)
        ctk.CTkLabel(self._topbar, text=titulo, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_PETROLEO).pack(side="left", padx=16)
        ctk.CTkLabel(self._topbar, text="Patrimônio › Bens › " + ("Editar" if self._bem_id else "Novo"),
                     font=ctk.CTkFont(size=11),
                     text_color="#888780").pack(side="left", padx=4)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16)

        scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=15)

        # ── Seção 1: Identificação ────────────────────────────────────────────
        sec1 = SecaoFormulario(scroll, "Identificação")
        sec1.pack(fill="x", pady=(0, 10))

        grid_tombo = ctk.CTkFrame(sec1, fg_color="transparent")
        grid_tombo.pack(fill="x", padx=14, pady=(0, 8))

        lbl_tombo_titulo = ctk.CTkLabel(grid_tombo, text="Número de tombo",
                                        text_color="#5F5E5A",
                                        font=ctk.CTkFont(size=11, weight="bold"),
                                        anchor="w")
        lbl_tombo_titulo.pack(anchor="w", pady=(0, 3))

        tombo_box = ctk.CTkFrame(grid_tombo, fg_color="#EAF4F3",
                                 corner_radius=6, border_width=1, border_color="#B9DCD8")
        tombo_box.pack(fill="x")
        self._lbl_tombo = ctk.CTkLabel(tombo_box, text="—", text_color=COR_PETROLEO,
                                       font=ctk.CTkFont(size=17, weight="bold", family="Consolas"))
        self._lbl_tombo.pack(side="left", padx=(12, 8), pady=8)
        self._lbl_tombo_dica = ctk.CTkLabel(
            tombo_box, text="", text_color="#14504C", font=ctk.CTkFont(size=10),
            justify="left")
        self._lbl_tombo_dica.pack(side="left", padx=(0, 12), pady=8)

        self._descricao = Campo(sec1, "Descrição", obrigatorio=True, largura=500)
        self._descricao.pack(fill="x", padx=14, pady=(8, 8))

        grid1 = ctk.CTkFrame(sec1, fg_color="transparent")
        grid1.pack(fill="x", padx=14, pady=(0, 12))
        grid1.grid_columnconfigure((0, 1), weight=1)

        self._marca_modelo = Campo(grid1, "Marca / modelo", largura=220)
        self._marca_modelo.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        self._lbl_localizacao = ctk.CTkLabel(grid1, text="Localização*", text_color="#5F5E5A",
                                             font=ctk.CTkFont(size=11, weight="bold"), anchor="w")
        self._lbl_localizacao.grid(row=0, column=1, sticky="nw", pady=(0, 3))
        self._opt_localizacao = ctk.CTkOptionMenu(
            grid1, values=["Carregando..."], width=220, height=34, corner_radius=6,
            fg_color=COR_CINZA_E, button_color=COR_PETROLEO_M, text_color="#3d3d3a")
        self._opt_localizacao.grid(row=0, column=1, sticky="ew",pady=(3, 0))

        # ── Seção 2: Aquisição ──────────────────────────────────────────────────
        sec2 = SecaoFormulario(scroll, "Aquisição — todos opcionais")
        sec2.pack(fill="x", pady=(0, 10))

        grid2 = ctk.CTkFrame(sec2, fg_color="transparent")
        grid2.pack(fill="x", padx=14, pady=(0, 12))
        grid2.grid_columnconfigure((0, 1, 2), weight=1)

        self._data_aquisicao = Campo(grid2, "Data de aquisição", placeholder="dd/mm/aaaa", largura=140)
        self._data_aquisicao.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        self._valor_aquisicao = Campo(grid2, "Valor de aquisição", placeholder="0,00", largura=140)
        self._valor_aquisicao.grid(row=0, column=1, padx=(0, 12), sticky="ew")

        self._nota_fiscal = Campo(grid2, "Nota fiscal", placeholder="Número da NF", largura=140)
        self._nota_fiscal.grid(row=0, column=2, sticky="ew")

        # ── Seção 3: Observação ─────────────────────────────────────────────────
        sec3 = SecaoFormulario(scroll, "Observação")
        sec3.pack(fill="x", pady=(0, 10))

        self._observacao = ctk.CTkTextbox(sec3, height=60, corner_radius=6,
                                          fg_color=COR_CINZA_E, text_color="#3d3d3a")
        self._observacao.pack(fill="x", padx=14, pady=(0, 12))

        # ── Rodapé ───────────────────────────────────────────────────────────────
        rodape = ctk.CTkFrame(scroll, fg_color="transparent")
        rodape.pack(fill="x", pady=8)

        ctk.CTkButton(rodape, text="Cancelar", width=110, height=34,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=lambda: self._on_navigate("bens_patrimoniais")).pack(side="left")

        direita = ctk.CTkFrame(rodape, fg_color="transparent")
        direita.pack(side="right")

        ctk.CTkButton(direita, text="Salvar e imprimir etiqueta",
                      width=210, height=34,
                      fg_color=COR_BRANCO, text_color=COR_PETROLEO_M,
                      border_width=1, border_color="#B9DCD8", hover_color=COR_CINZA_E,
                      command=self._salvar_e_imprimir).pack(side="left", padx=(0, 8))

        ctk.CTkButton(direita, text="Salvar", width=140, height=34,
                      fg_color=COR_PETROLEO_M, hover_color=COR_PETROLEO,
                      command=self._salvar).pack(side="left")

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar_preview_tombo(self):
        try:
            tombo = self._servico.previsualizar_tombo(self._usuario.id)
            self._lbl_tombo.configure(text=tombo)
            self._lbl_tombo_dica.configure(
                text="Gerado automaticamente ao salvar\nSequência contínua · imutável")
        except PatrimonioError as exc:
            self._lbl_tombo.configure(text="—")
            self._lbl_tombo_dica.configure(text=str(exc))
        self._carregar_localizacoes()

    def _carregar_localizacoes(self, localizacao_atual_id: int = None):
        try:
            self._localizacoes = self._servico.listar_localizacoes(self._usuario.id)
        except Exception as exc:
            logger.error("Erro ao carregar localizações: %s", exc)
            self._banner.erro(f"Erro ao carregar localizações: {exc}")
            self._localizacoes = []

        labels = [loc.nome_completo for loc in self._localizacoes]
        if not labels:
            labels = ["Nenhuma localização cadastrada"]
        self._opt_localizacao.configure(values=labels)

        if localizacao_atual_id is not None:
            atual = next((loc for loc in self._localizacoes if loc.id == localizacao_atual_id), None)
            if atual:
                self._opt_localizacao.set(atual.nome_completo)
                # Editar não move o bem (RN-11) — localização fica travada aqui.
                self._opt_localizacao.configure(state="disabled")
                self._lbl_localizacao.configure(
                    text="Localização* — mudança de lotação é feita em Movimentar/Baixar")
        elif labels:
            self._opt_localizacao.set(labels[0])

    def _preencher_bem(self, bem_id: int):
        try:
            bem = self._servico.obter_bem(self._usuario.id, bem_id)
        except PatrimonioError as exc:
            logger.error("Erro ao carregar bem %s: %s", bem_id, exc)
            self._banner.erro(str(exc))
            return

        self._lbl_tombo.configure(text=bem.tombo)
        self._lbl_tombo_dica.configure(text="Tombo emitido — imutável (RN-09)")
        self._descricao.set(bem.descricao)
        if bem.marca_modelo:
            self._marca_modelo.set(bem.marca_modelo)
        if bem.data_aquisicao:
            self._data_aquisicao.set(bem.data_aquisicao.strftime("%d/%m/%Y"))
        if bem.valor_aquisicao is not None:
            self._valor_aquisicao.set(str(bem.valor_aquisicao))
        if bem.nota_fiscal:
            self._nota_fiscal.set(bem.nota_fiscal)
        if bem.observacao:
            self._observacao.insert("1.0", bem.observacao)

        self._carregar_localizacoes(localizacao_atual_id=bem.localizacao_id)

    # ── Submit ────────────────────────────────────────────────────────────────

    def _montar_dados(self):
        """Valida o formulário e devolve DadosBem, ou None se inválido (já mostra o erro no banner)."""
        if not self._descricao.validar():
            return None

        loc_label = self._opt_localizacao.get()
        localizacao = next((loc for loc in self._localizacoes if loc.nome_completo == loc_label), None)
        if not localizacao:
            self._banner.erro("Selecione uma localização válida.")
            return None

        return DadosBem(
            descricao=self._descricao.get(),
            localizacao_id=localizacao.id,
            marca_modelo=self._marca_modelo.get() or None,
            data_aquisicao=self._parse_data(self._data_aquisicao.get()),
            valor_aquisicao=self._parse_valor(self._valor_aquisicao.get()),
            nota_fiscal=self._nota_fiscal.get() or None,
            observacao=self._observacao.get("1.0", "end").strip() or None,
        )

    def _salvar(self):
        dados = self._montar_dados()
        if dados is None:
            return

        try:
            if self._bem_id:
                self._servico.editar_bem(self._bem_id, dados, usuario_id=self._usuario.id)
                self._banner.sucesso("Bem atualizado com sucesso.")
            else:
                bem = self._servico.cadastrar_bem(dados, usuario_id=self._usuario.id)
                self._banner.sucesso(f"Bem {bem.tombo} cadastrado com sucesso.")
            self._on_navigate("bens_patrimoniais")
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
        except Exception as exc:
            logger.error("Erro ao salvar bem: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")

    # ── Salvar e imprimir etiqueta ───────────────────────────────────────────────

    def _salvar_e_imprimir(self):
        dados = self._montar_dados()
        if dados is None:
            return

        try:
            if self._bem_id:
                self._servico.editar_bem(self._bem_id, dados, usuario_id=self._usuario.id)
                self._bem_id_para_imprimir = self._bem_id
            else:
                bem = self._servico.cadastrar_bem(dados, usuario_id=self._usuario.id)
                self._bem_id_para_imprimir = bem.id
        except PatrimonioError as exc:
            self._banner.erro(str(exc))
            return
        except Exception as exc:
            logger.error("Erro ao salvar bem: %s", exc)
            self._banner.erro(f"Erro ao salvar: {exc}")
            return

        if self._painel_impressora:
            self._painel_impressora.destroy()
        self._painel_impressora = SeletorImpressora(
            self, servico=self._servico, usuario=self._usuario,
            on_confirmar=self._ao_confirmar_impressora,
            on_cancelar=self._ao_cancelar_impressao,
        )
        self._painel_impressora.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.45, relheight=0.5)

    def _ao_cancelar_impressao(self):
        if self._painel_impressora:
            self._painel_impressora.destroy()
            self._painel_impressora = None
        self._on_navigate("bens_patrimoniais")

    def _ao_confirmar_impressora(self, nome_impressora: str):
        if self._painel_impressora:
            self._painel_impressora.destroy()
            self._painel_impressora = None
        try:
            self._servico.gerar_etiquetas(
                [self._bem_id_para_imprimir], SaidaEtiqueta.impressora_cabo,
                usuario_id=self._usuario.id, nome_impressora=nome_impressora)
            self._banner.sucesso("Bem salvo e etiqueta enviada para impressão.")
        except PatrimonioError as exc:
            self._banner.erro(f"Bem salvo, mas falhou ao imprimir: {exc}")
        except Exception as exc:
            logger.error("Erro ao imprimir etiqueta: %s", exc)
            self._banner.erro(f"Bem salvo, mas falhou ao imprimir: {exc}")
        self._on_navigate("bens_patrimoniais")

    def limpar_memoria(self):
        """Chamado pelo app.py ao sair da tela — fecha painéis flutuantes abertos."""
        if self._painel_impressora is not None:
            self._painel_impressora.destroy()
            self._painel_impressora = None

    @staticmethod
    def _parse_data(texto: str):
        if not texto:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(texto, "%d/%m/%Y").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_valor(texto: str):
        if not texto:
            return None
        from decimal import Decimal, InvalidOperation
        try:
            return Decimal(texto.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return None
