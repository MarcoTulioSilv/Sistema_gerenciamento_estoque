"""
gui · telas · t11_relatorios.py
Tela T-11 — Central de relatórios sob demanda (UC-11 a UC-14, RF-15 a RF-17, RF-20, RF-22).
Gestora e TI podem gerar e enviar qualquer relatório imediatamente.
"""
import logging
from datetime import date, timedelta, datetime
import threading 
import customtkinter as ctk
from tkinter import messagebox
from gui.componentes.form_widgets import FeedbackBanner, Campo
from Modulo_03_relatorios import RelatorioService 

logger = logging.getLogger(__name__)
 
COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_BRANCO = "#FFFFFF"
COR_VERM   = "#A32D2D"
COR_VERDE  = "#1D9E75"
 
 
class TelaCentralRelatorios(ctk.CTkFrame):
    """Central de relatórios — geração e envio imediato por e-mail."""
 
    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
        self._usuario     = usuario
        self._on_navigate = on_navigate
        self._construir()
        self._carregar_ultimo_envio()
 
    # ── Construção ────────────────────────────────────────────────────────────
 
    def _construir(self):
        # Topbar
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Central de relatórios",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16)
 
        self._banner = FeedbackBanner(self)
        self._banner.pack(fill="x", padx=16, pady=(8, 0))
 
        scroll = ctk.CTkScrollableFrame(self, fg_color=COR_CINZA_E, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=12)
 
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)
 
        # ── Card 1: Movimentação ──────────────────────────────────────────────
        self._card_mov = _CardRelatorio(
            scroll,
            titulo   = "Relatório de movimentação",
            descricao= "Entradas e saídas por período. Inclui produto, lote, NF, tipo e usuário.",
            cor_btn  = COR_AZUL_M,
            texto_btn= "Gerar e enviar XLSX",
        )
        self._card_mov.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
 
        # Seleção de período dentro do card
        per_frame = ctk.CTkFrame(self._card_mov, fg_color="transparent")
        per_frame.pack(fill="x", padx=14, pady=(0, 6))
 
        ctk.CTkLabel(per_frame, text="De:", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._dt_ini = ctk.CTkEntry(per_frame, placeholder_text="DD/MM/AAAA",
                                     width=110, height=28, corner_radius=6)
        self._dt_ini.pack(side="left", padx=(4, 12))
        self._dt_ini.insert(0, _primeiro_do_mes())
 
        ctk.CTkLabel(per_frame, text="Até:", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._dt_fim = ctk.CTkEntry(per_frame, placeholder_text="DD/MM/AAAA",
                                     width=110, height=28, corner_radius=6)
        self._dt_fim.pack(side="left", padx=4)
        self._dt_fim.insert(0, date.today().strftime("%d/%m/%Y"))
 
        self._card_mov.configurar_acao(self._gerar_movimentacao)
        self._lbl_ult_mov = self._card_mov.label_ultimo_envio()
 
        # ── Card 2: Estoque atual ─────────────────────────────────────────────
        self._card_est = _CardRelatorio(
            scroll,
            titulo   = "Relatório de estoque atual",
            descricao= "Posição completa por produto e lote: quantidade, vencimento e situação.\nLotes vencidos destacados em vermelho.",
            cor_btn  = COR_AZUL_M,
            texto_btn= "Gerar e enviar XLSX",
        )
        self._card_est.grid(row=0, column=1, pady=(0, 8), sticky="nsew")
        self._card_est.configurar_acao(self._gerar_estoque)
        self._lbl_ult_est = self._card_est.label_ultimo_envio()
 
        # ── Card 3: A vencer ─────────────────────────────────────────────────
        self._card_venc = _CardRelatorio(
            scroll,
            titulo   = "Produtos próximos ao vencimento",
            descricao= "Lotes com vencimento nos próximos 30 dias,\nordenados por data crescente.",
            cor_btn  = COR_AZUL_M,
            texto_btn= "Gerar e enviar XLSX",
        )
        self._card_venc.grid(row=1, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        self._card_venc.configurar_acao(self._gerar_a_vencer)
        self._lbl_ult_venc = self._card_venc.label_ultimo_envio()
 
        # ── Card 4: Lotes vencidos ────────────────────────────────────────────
        self._card_vencido = _CardRelatorio(
            scroll,
            titulo    = "Lotes vencidos em estoque",
            descricao = "Lotes com data anterior a hoje e saldo > 0.\nTodos destacados em vermelho — providencie o descarte.",
            cor_btn   = COR_VERM,
            texto_btn = "Gerar e enviar XLSX",
            alerta    = True,
        )
        self._card_vencido.grid(row=1, column=1, pady=(0, 8), sticky="nsew")
        self._card_vencido.configurar_acao(self._gerar_vencidos)
        self._lbl_ult_vencido = self._card_vencido.label_ultimo_envio()
 
        # Rodapé informativo
        ctk.CTkFrame(scroll, fg_color=COR_BRANCO, corner_radius=6,
                     border_width=1, border_color=COR_CINZA_B,
                     height=36).grid(row=2, column=0, columnspan=2,
                                     sticky="ew", pady=(0, 4))
        self._lbl_email = ctk.CTkLabel(
            scroll,
            text="Todos os relatórios são enviados por e-mail para o endereço configurado em Administração → Config. Gmail.",
            text_color="#888780", font=ctk.CTkFont(size=10))
        self._lbl_email.grid(row=2, column=0, columnspan=2,
                              padx=14, pady=8, sticky="w")
 
    # ── Dados ─────────────────────────────────────────────────────────────────
 
    def _carregar_ultimo_envio(self):
        """Preenche os labels de último envio com dados do banco."""
        try:
            
            ags = {a.tipo_relatorio: a for a in RelatorioService.listar_agendamentos()}
            for tipo, lbl in [
                ("movimentacao",   self._lbl_ult_mov),
                ("estoque_atual",  self._lbl_ult_est),
                ("a_vencer",       self._lbl_ult_venc),
                ("lotes_vencidos", self._lbl_ult_vencido),
            ]:
                ag = ags.get(tipo)
                if ag and ag.ultimo_envio:
                    lbl.configure(
                        text=f"Último envio: {ag.ultimo_envio.strftime('%d/%m/%Y %H:%M')}")
                else:
                    lbl.configure(text="Último envio: nunca")
        except Exception as exc:
            logger.warning("Erro ao carregar último envio: %s", exc)
 
    # ── Ações ─────────────────────────────────────────────────────────────────
 
    def _gerar_movimentacao(self):
        ini = _parse_date(self._dt_ini.get())
        fim = _parse_date(self._dt_fim.get())
        if not ini or not fim:
            self._banner.erro("Informe datas válidas no formato DD/MM/AAAA.")
            return
        if ini > fim:
            self._banner.erro("Data inicial não pode ser posterior à data final.")
            return
        self._executar("movimentacao",
                       lambda: __import__("Modulo_03_relatorios",
                                          fromlist=["RelatorioService"]
                                          ).RelatorioService.gerar_e_enviar_movimentacao(ini, fim))
 
    def _gerar_estoque(self):
        self._executar("estoque_atual",
                       lambda: __import__("Modulo_03_relatorios",
                                          fromlist=["RelatorioService"]
                                          ).RelatorioService.gerar_e_enviar_estoque_atual())
 
    def _gerar_a_vencer(self):
        self._executar("a_vencer",
                       lambda: __import__("Modulo_03_relatorios",
                                          fromlist=["RelatorioService"]
                                          ).RelatorioService.gerar_e_enviar_a_vencer())
 
    def _gerar_vencidos(self):
        self._executar("lotes_vencidos",
                       lambda: __import__("Modulo_03_relatorios",
                                          fromlist=["RelatorioService"]
                                          ).RelatorioService.gerar_e_enviar_lotes_vencidos())
 
    def _executar(self, tipo: str, fn):
        """Executa a geração em thread separada para não travar a GUI."""
        
 
        def _run():
            try:
                fn()
                # Atualiza GUI na thread principal
                self.after(0, lambda: self._banner.sucesso(
                    f"Relatório '{tipo.replace('_',' ')}' gerado e enviado por e-mail."))
                self.after(0, self._carregar_ultimo_envio)
            except Exception as exc:
                logger.error("Erro ao gerar relatório '%s': %s", tipo, exc)
                self.after(0, lambda: self._banner.erro(f"Erro: {exc}"))
 
        self._banner.sucesso("Gerando relatório... aguarde.")
        threading.Thread(target=_run, daemon=True).start()
 
 
# ── Componentes auxiliares ────────────────────────────────────────────────────
 
class _CardRelatorio(ctk.CTkFrame):
    """Card individual de relatório com título, descrição e botão de ação."""
 
    def __init__(self, master, titulo, descricao, cor_btn, texto_btn,
                 alerta=False, **kwargs):
        borda = "#F09595" if alerta else "#E8E6DE"
        super().__init__(master, fg_color="#FFFFFF", corner_radius=8,
                         border_width=1, border_color=borda, **kwargs)
        self._btn = None
 
        cor_titulo = "#A32D2D" if alerta else "#1F4E79"
        ctk.CTkLabel(self, text=titulo,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=cor_titulo, anchor="w",
                     wraplength=340).pack(fill="x", padx=14, pady=(12, 0))
 
        ctk.CTkLabel(self, text=descricao,
                     font=ctk.CTkFont(size=11), text_color="#5F5E5A",
                     anchor="w", justify="left",
                     wraplength=340).pack(fill="x", padx=14, pady=(4, 8))
 
        self._lbl_envio = ctk.CTkLabel(
            self, text="Último envio: —",
            font=ctk.CTkFont(size=10), text_color="#888780", anchor="w")
        self._lbl_envio.pack(fill="x", padx=14)
 
        self._btn = ctk.CTkButton(
            self, text=texto_btn, height=32,
            fg_color=cor_btn, hover_color="#1a5276",
            font=ctk.CTkFont(size=12))
        self._btn.pack(fill="x", padx=14, pady=12)
 
    def configurar_acao(self, fn):
        self._btn.configure(command=fn)
 
    def label_ultimo_envio(self) -> ctk.CTkLabel:
        return self._lbl_envio
 
 
# ── Utilitários ───────────────────────────────────────────────────────────────
 
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