"""
gui · telas · t13_estoque_minimo.py
Tela T-13 — Configuração de estoque mínimo por produto (UC-08, RF-14, RN-04).
Gestora e TI podem visualizar e alterar o estoque mínimo de cada produto.
Edição inline — sem abrir nova tela; Salvar por linha (não em lote).
"""
import logging
from Modulo_06_dados import get_session, get_read_session, Produto
import customtkinter as ctk
from gui.componentes.form_widgets import FeedbackBanner

logger = logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERM   = "#A32D2D"
COR_VERDE  = "#1D9E75"

_SITUACAO_COR = {
    "Abaixo do mínimo": ("#FAEEDA", "#854F0B"),
    "Normal":           ("#EAF3DE", "#27500A"),
    "Sem controle":     ("#F1EFE8", "#5F5E5A"),
}

_COLUNAS = [
    ("Produto",         220),
    ("Centro",           90),
    ("Saldo atual",      90),
    ("Estoque mínimo",  120),
    ("Situação",        120),
    ("",                 80),
]


class TelaEstoqueMinimo(ctk.CTkFrame):
    """T-13 — Configuração de estoque mínimo por produto."""

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._dados: list[dict] = []
        self._linhas: list[dict] = []
        self._construir()
        self._carregar()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir(self):
        # Topbar
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Configuração de estoque mínimo",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(topbar, text="Atualizar", width=90, height=28,
                      fg_color=COR_BRANCO, text_color="#161614",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E, font=ctk.CTkFont(size=11),
                      command=self._carregar).pack(side="right", padx=16, pady=8)

        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))

        # Filtros
        filt = ctk.CTkFrame(self, fg_color="transparent")
        filt.pack(fill="x", padx=16, pady=(10, 0))

        self._entry_busca = ctk.CTkEntry(
            filt, placeholder_text="Buscar produto...",
            height=32, width=280, corner_radius=6)
        self._entry_busca.pack(side="left")
        self._entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        self._opt_centro = ctk.CTkOptionMenu(
            filt, values=["Todos os centros", "Almoxarifado", "Farmacia"],
            width=150, height=32, corner_radius=6,
            fg_color=COR_BRANCO, button_color=COR_AZUL_M, text_color="#161614",
            command=lambda _: self._filtrar())
        self._opt_centro.pack(side="left", padx=8)

        ctk.CTkButton(filt, text="Limpar", width=70, height=32,
                      fg_color=COR_BRANCO, text_color="#161614",
                      border_width=1, border_color=COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=self._limpar_filtros).pack(side="left")

        # Cabeçalho da tabela
        hdr = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B)
        hdr.pack(fill="x", padx=16, pady=(10, 0))
        for col, (txt, largura) in enumerate(_COLUNAS):
            ctk.CTkLabel(hdr, text=txt.upper(), text_color="#888780",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         width=largura, anchor="w").grid(
                row=0, column=col, padx=6, pady=6, sticky="w")

        # Área de scroll
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E,
                                               corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        # Rodapé com nota RN-04
        rod = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=0,
                           border_width=1, border_color=COR_CINZA_B, height=28)
        rod.pack(fill="x", padx=16, pady=(0, 8))
        rod.pack_propagate(False)
        ctk.CTkLabel(rod,
                     text="Valor 0 = sem controle de mínimo para este produto (RN-04)."
                          " Alterações registradas em log com usuário e data/hora (RNF-06).",
                     text_color="#888780", font=ctk.CTkFont(size=10)).pack(
            side="left", padx=10)

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        """Carrega produtos ativos com saldo calculado a partir dos lotes."""
        try:
            with get_read_session() as s:
                produtos = (s.query(Produto)
                              .filter_by(ativo=True)
                              .order_by(Produto.nome)
                              .all())
                dados = []
                for p in produtos:
                    saldo = sum(
                        l.quantidade_atual for l in p.lotes
                        if l.quantidade_atual > 0
                    )
                    dados.append({
                        "id":             p.id,
                        "nome":           p.nome,
                        "centro":         p.centro_alocacao.value.capitalize(),
                        "estoque_minimo": p.estoque_minimo,
                        "saldo":          saldo,
                    })
            self._dados = dados
            self._renderizar(dados)
        except Exception as exc:
            logger.error("Erro ao carregar produtos: %s", exc)
            self._banner.erro(f"Erro ao carregar produtos: {exc}")

    def _filtrar(self):
        busca  = self._entry_busca.get().lower()
        centro = self._opt_centro.get()
        filtrados = [
            d for d in self._dados
            if (busca in d["nome"].lower())
            and (centro == "Todos os centros"
                 or d["centro"].lower() in centro.lower())
        ]
        self._renderizar(filtrados)

    def _limpar_filtros(self):
        self._entry_busca.delete(0, "end")
        self._opt_centro.set("Todos os centros")
        self._renderizar(self._dados)

    # ── Renderização ──────────────────────────────────────────────────────────

    def _renderizar(self, dados: list[dict]):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._linhas.clear()

        if not dados:
            ctk.CTkLabel(self._scroll, text="Nenhum produto encontrado.",
                         text_color="#888780",
                         font=ctk.CTkFont(size=12)).pack(pady=24)
            return

        for i, d in enumerate(dados):
            bg = COR_BRANCO if i % 2 == 0 else COR_CINZA_E
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            # Nome do produto
            ctk.CTkLabel(row, text=d["nome"][:28], text_color="#3d3d3a",
                         font=ctk.CTkFont(size=11), width=220,
                         anchor="w").grid(row=0, column=0, padx=6, pady=7, sticky="w")

            # Centro
            ctk.CTkLabel(row, text=d["centro"], text_color="#3d3d3a",
                         font=ctk.CTkFont(size=11), width=90,
                         anchor="w").grid(row=0, column=1, padx=6, pady=7, sticky="w")

            # Saldo atual
            ctk.CTkLabel(row, text=str(d["saldo"]), text_color="#3d3d3a",
                         font=ctk.CTkFont(size=11, weight="bold"), width=90,
                         anchor="center").grid(row=0, column=2, padx=6, pady=7)

            # Campo de edição do mínimo — pré-preenchido
            entry_min = ctk.CTkEntry(row, width=80, height=28, corner_radius=4)
            entry_min.insert(0, str(d["estoque_minimo"]))
            entry_min.grid(row=0, column=3, padx=6, pady=7)

            # Badge de situação calculada em tempo real
            situacao = _calcular_situacao(d["saldo"], d["estoque_minimo"])
            fg_s, tc_s = _SITUACAO_COR.get(situacao, ("#F1EFE8", "#5F5E5A"))
            ctk.CTkLabel(row, text=situacao,
                         fg_color=fg_s, text_color=tc_s,
                         font=ctk.CTkFont(size=9, weight="bold"),
                         corner_radius=6, padx=6, pady=2, width=120).grid(
                row=0, column=4, padx=6, pady=7)

            # Botão salvar por linha (RNF-06: alteração registrada em log)
            pid = d["id"]
            ctk.CTkButton(
                row, text="Salvar", width=64, height=26,
                fg_color=COR_AZUL_M, hover_color="#1a5276",
                font=ctk.CTkFont(size=11),
                command=lambda p=pid, e=entry_min: self._salvar_linha(p, e),
            ).grid(row=0, column=5, padx=6, pady=7)

            self._linhas.append({"id": pid, "entry": entry_min, "dados": d})

    # ── Persistência ──────────────────────────────────────────────────────────

    def _salvar_linha(self, produto_id: int, entry: ctk.CTkEntry):
        valor_str = entry.get().strip()
        try:
            novo_min = int(valor_str)
            if novo_min < 0:
                raise ValueError
        except ValueError:
            self._banner.erro(
                "Valor inválido. Informe um número inteiro ≥ 0.")
            return

        try:
            with get_session() as s:
                produto = s.query(Produto).filter_by(id=produto_id).first()
                if produto:
                    produto.estoque_minimo = novo_min

            # Atualizar cache local para filtro continuar correto
            for linha in self._linhas:
                if linha["id"] == produto_id:
                    linha["dados"]["estoque_minimo"] = novo_min
                    break

            self._banner.sucesso("Estoque mínimo atualizado com sucesso.")
            logger.info("Estoque mínimo do produto %s → %s (usuário: %s).",
                        produto_id, novo_min, self._usuario.login)
        except Exception as exc:
            logger.error("Erro ao salvar estoque mínimo (produto %s): %s", produto_id, exc)
            self._banner.erro(f"Erro ao salvar: {exc}")


# ── Utilitários ───────────────────────────────────────────────────────────────

def _calcular_situacao(saldo: int, minimo: int) -> str:
    """Retorna rótulo de situação para o badge."""
    if minimo == 0:
        return "Sem controle"
    if saldo <= minimo:
        return "Abaixo do mínimo"
    return "Normal"