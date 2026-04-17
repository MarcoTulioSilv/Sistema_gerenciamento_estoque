import os
import customtkinter as ctk
from datetime import datetime
from gui.telas.t01_login import TelaLogin
from gui.telas.placeholder import TelaPlaceholder
from tkinter import messagebox
from Modulo_01_autenticacao import SessionManager
from gui.telas.t02_inicio import TelaInicio
from gui.telas.t03_produtos import TelaProdutos
from gui.telas.t21_troca_senha import TelaTrocaSenha
# tema global
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

COR_AZUL      = "#1F4E79"
COR_AZUL_M    = "#2E75B6"
COR_SIDEBAR   = "#1F4E79"
COR_SIDEBAR_H = "#2E75B6"   # hover
COR_SIDEBAR_A = "#2E75B6"   # ativo
COR_CINZA_E   = "#F2F1ED"
COR_TEXTO     = "#3d3d3a"
COR_VERMELHO  = "#A32D2D"

class SCEApp(ctk.CTk):
    # Janela raiz do sistema, gerencia login e navegação entre telas
    def __init__(self):
        super().__init__()

        self.title("Sistema de Controle de Estoque - Centro de Uronefrologia")
        self.geometry("1100x600")
        self.minsize(900, 600)
        self.configure(fg_color=COR_CINZA_E)

        # Estado dee sessão
        self.usuario_logado = None #objeto do usuário logado
        self.session_timer = None

        #exibe tela de login na inicialização
        self._monstrar_login()

#---- login/ logout ----
    def _monstrar_login(self):
        """limpa a janela e exibe a tela de login"""        
        for widget in self.winfo_children():
            widget.destroy()
        TelaLogin(self, on_login_success=self._on_login_success).pack(fill="both", expand=True)
    
    def _on_login_success(self, usuario):
        """callback chamaado pelo mod-01 apos autenticação bem sucedida"""
        self.usuario_logado = usuario
        SessionManager.iniciar_sessao(usuario)
        self._iniciar_timer_sessao()
        self._construir_layout_principal()

    def logout(self):
        """encerra sessão e volta para tela de login"""
        if self.session_timer:
            self.after_cancel(self.session_timer)
        SessionManager.encerrar_sessao()
        self.usuario_logado = None
        self._monstrar_login()

#----- sessão ---------------------------------------------------------------------------------
    def _iniciar_timer_sessao(self):
        
        timeout_min = int(os.getenv("SESSION_TIMEOUT_MIN", 30))
        timeout_ms = timeout_min * 60 * 1000
        if self.session_timer:
            self.after_cancel(self.session_timer)
        self.session_timer = self.after(timeout_ms, self._sessao_expirada)
    
    def resetar_timer_sessao(self):
        """chamado por telas para resetar o timer a cada interação do usuário"""
        self._iniciar_timer_sessao()
    
    def _sessao_expirada(self):
       
        messagebox.showinfo("Sessão Expirada", "Sua sessão expirou por inatividade. Faça login novamente.")
        self.logout()
        """ tecnico deve ter tempo de sessão maior, dash board não deve expirar """

#---- layout principal--------------------------------------------------------------------------------------

    def _construir_layout_principal(self):
        """Monta a estrutura de 3 faixas, titlebar, conteudo(sidebar + main)"""
        for w in self.winfo_children():
            w.destroy() 
        #titlebar
        self._titlebar = TitleBar(self, usuario=self.usuario_logado, on_logout=self.logout)
        self._titlebar.pack(fill="x")

        #corpo: sidebar + main
        corpo= ctk.CTkFrame(self, fg_color=COR_CINZA_E)
        corpo.pack(fill="both", expand=True)
        corpo.grid_columnconfigure(1, weight=1)
        corpo.grid_rowconfigure(0, weight=1)

        self._sidebar = Sidebar(corpo, usuario=self.usuario_logado, on_navigate=self._navegar)
        self._sidebar.grid(row=0, column=0, sticky="nsw")

        self._area_conteudo = ctk.CTkFrame(corpo, fg_color=COR_CINZA_E)
        self._area_conteudo.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        #exibe tela inicial por padrão
        self._navegar("troca_senha")

    def _navegar(self, destino: str):
        """troca o conteudo da area principal pela tela indicada """
        self.resetar_timer_sessao()
        for w in self._area_conteudo.winfo_children():
            w.destroy()
        
        tela = self._resolver_tela(destino)
        if tela:
            tela.pack(fill="both", expand=True)
    
    def _resolver_tela(self, destino: str):
        """mapeia o indicador de destino para a classe de tela correspondente"""
        nav= self._on_navigate_com_extra
        # sprint 1: telas reia de autenticação plugadas.
        # telas reais colocadas aqui nas proximas sprints
        if destino=="inicio":
            return TelaInicio(self._area_conteudo, usuario=self.usuario_logado)
        if destino=="troca_senha":
            return TelaTrocaSenha(self._area_conteudo, usuario=self.usuario_logado)
        #______ Sprint 2A_ MOD-02 cadastros
        if destino=="produtos":
            return TelaProdutos(self._area_conteudo, usuario= self.usuario_logado, on_navigate= nav)
            
        nomes = {
            "fornecedores":   "Tela de Fornecedores - T-04",
            "entrada_manual": "Tela de Entrada Manual - T-07",
            "importar_nfe":   "Tela de Importação de NF-e - T-08",
            "retirada":       "Tela de Retirada - T-09",
            "posicao":        "Tela de Posição de Estoque - T-10",
            "dashboard":      "Tela de Dashboard - T-11",
            "relatorios":     "Relatórios — T-11",
            "agendamento":    "Agendamento — T-12",
            "estoque_minimo": "Estoque Mínimo — T-13",
            "usuarios":       "Usuários — T-15",
            "gmail":          "Config. Gmail — T-17",
            "backup":         "Backup — T-18",
            "log":            "Log de Operações — T-19",
        }
        titulo = nomes.get(destino, destino)
        return TelaPlaceholder(self._area_conteudo, titulo=titulo)
    
    def _on_navigate_com_extra(self, destino: str, extra=None):
        """Versão do _navegar que aceita parâmetro extra(ex: produto_id)"""
        self.resetar_timer_sessao()
        for w in self._area_conteudo.winfo_children():
            w.destroy()
        tela= self._resolver_tela(destino, extra= extra)
        if tela:
            tela.pack(fill="both", expand= True)

#---- Componentes da janela principal (titlebar, sidebar) --------------------------------------------------------------

class TitleBar(ctk.CTkFrame):
    """Barra de titulo superior- CP-01"""

    def __init__(self, master, usuario, on_logout):
        super().__init__(master, fg_color=COR_AZUL, height=36, corner_radius=0)
        self.pack_propagate(False)
        
        ctk.CTkLabel(
            self, text= "Sistema de Controle de Estoque - Centro de Uro-nefrologia V1.0",
            text_color="white", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=8)

        #Informações do usuário e botão de logout
        frame_direita = ctk.CTkFrame(self, fg_color="transparent")
        frame_direita.pack(side="right", padx=12)


        hora= datetime.now().strftime("%d/%m/%Y %H:%M")
        nome_perfil= f"{usuario.nome} | ({usuario.perfil.value.capitalize()})"
        ctk.CTkLabel(
            frame_direita,
            text= f"{nome_perfil} . {hora}",
            text_color="white", font=ctk.CTkFont(size=11)
        ).pack(side="left")

        ctk.CTkButton(
            frame_direita, text="Sair",width=50, height=24,
            fg_color=COR_AZUL_M, hover_color="#1a5276", text_color="white",
            font=ctk.CTkFont(size=11),command=on_logout
        ).pack(side="left")
    
class Sidebar(ctk.CTkFrame):
    """Menu lateral com itens por perfil - CP-02"""
    MENU= [
        ("__label__",    "Estoque", None),
        ("inicio",       "Início",       ["tecnico", "adimin","ti"]),
        ("produtos",     "Produtos",     ["ti", "tecnico", "admin"]),
        ("fornecedores", "Fornecedores", ["admin", "tecnico"]),
        ("__label__",    "Movimentações", None),
        ("entrada_manual", "Entrada Manual", ["admin", "tecnico"]),
        ("importar_nfe", "Importar NF-e",    ["admin", "tecnico"]),
        ("retirada", "Retirada",             ["admin", "tecnico"]),
        ("__label__", "Consulta", None),
        ("posicao", "Posição de Estoque", ["admin", "tecnico", "ti"]),
        ("dashboard", "Dashboard",        ["admin", "tecnico", "ti"]),
        ("__label__", "Relatórios", None),
        ("relatorios", "Gerar Relatórios",      ["admin", "ti"]),
        ("agendamento", "Agendamento",          ["ti"]),
        ("estoque_minimo","Estoque Mínimo" ,["admin", "ti"]),
        ("__label__", "Configurações", None),
        ("usuarios",    "Gerenciamento de Usuários" , ["ti"]),
        ("gmail",       "Configurações Gmail" ,          ["ti"]),
        ("backup",      "Backup do Sistema" ,           ["ti"]),
        ("log",         "Log de Operações" ,               ["ti"]),
    ]

    def __init__(self, master, usuario, on_navigate):
        super().__init__(master, fg_color=COR_SIDEBAR, width=200,corner_radius=0)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._perfil = usuario.perfil.value
        self._botoes = {}
        self._ativo= None
        self._construir()

    def _construir(self):
        for item in self.MENU:
            destino, label, perfis = item

            if destino == "__label__":
                ctk.CTkLabel(
                    self, text=label.upper(),
                    text_color="#7fa8cc",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    anchor="w",
                ).pack(fill="x", padx=14, pady=(10,2))
                continue

            permitido= perfis and self._perfil in perfis
            btn = ctk.CTkButton(
                self,
                text=f"  {label}",
                anchor="w",
                fg_color="transparent",
                text_color="white" if permitido else "#5a7a99",
                hover_color=COR_SIDEBAR_H if permitido else COR_SIDEBAR,
                height=32,
                corner_radius=6,
                font=ctk.CTkFont(size=12),
                state="normal" if permitido else "disabled",
                command=(lambda d=destino: self._clicar(d)) if permitido else None,
            )
            btn.pack(fill="x", padx=6, pady=1)
            self._botoes[destino]= btn

    def _clicar(self, destino: str):
        # Remove destaque anterior 
        if self._ativo and self._ativo in self._botoes:
            self._botoes[self._ativo].configure(fg_color="transparent")
        # Destaca ativo
        self._ativo = destino
        self._botoes[destino].configure(fg_color=COR_SIDEBAR_A)
        self._on_navigate(destino)
