"""
gui. telas . t01_login.py
tela T-01 - login
Sprint 1 implementará o AuthenService real.
Srint 0: estrutura visual completa, autenticação integrada com MOD-01.
"""
import os
from PIL import Image
import customtkinter as ctk
from typing import Callable
from Modulo_01_autenticacao import AuthService
from gui.componentes.form_widgets import FeedbackBanner

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_AZUL_L = "#D6E4F0"
COR_ERRO   = "#A32D2D"
COR_CINZA_E  = "#F2F1ED"
COR_FUNDO  = "#D6E4F0"

class TelaLogin(ctk.CTkFrame):
    """Tela de autenticação- todos os perfis (UC-01)"""

    MAX_TENTATIVAS = 5
    BLOQUEIO_MS = 5*60*1000 #5 minutos

    def __init__(self, master, on_login_success: Callable):
        super().__init__(master, fg_color=COR_FUNDO, corner_radius=0)
        self._on_sucess = on_login_success
        self._tentativas = 0
        self._bloqueado = False
        self._construir()
    
    def _construir(self):
        # --- 1. CONFIGURAÇÃO DA IMAGEM DE FUNDO ---
        caminho_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_assets = os.path.join(os.path.dirname(os.path.dirname(caminho_atual)), "assets")
        caminho_logo = os.path.join(caminho_assets, "logo_Centro_Uro_Nefrologia_sem_fundo.png")

        # Se a imagem de fundo existir, ela preenche a tela
        if os.path.exists(caminho_logo):
            bg_image = ctk.CTkImage(
                light_image=Image.open(caminho_logo),
                dark_image=Image.open(caminho_logo),
                size=(1920, 1080) # Tamanho amplo para cobrir monitores comuns
            )
            # O Label com a imagem usa o .place() para preencher tudo e ficar atrás do grid
            lbl_bg = ctk.CTkLabel(self, text="", image=bg_image)
            lbl_bg.place(relx=0.465, rely=0.6, anchor="center")

    # --- 2. POSICIONAMENTO DO CARD (CENTRO-DIREITA) ---
        
        # Criação do card com fundo transparente e borda
        card = ctk.CTkFrame(self, width=360, fg_color="transparent", 
                            corner_radius=16, border_width=2, border_color="#353535")
        
        card.grid_propagate(False)
        card.configure(height=416)

        card.place(x=1300, y=255)

        # --- 4. CABEÇALHO ---
        ctk.CTkLabel(card, text="SCE- Sistema de Controle de Estoque \n Centro de Uro-Nefrologia", text_color=COR_AZUL,
                    font=ctk.CTkFont(size=16, weight="bold")).place(relx=0.5, rely=0.1, anchor="n")
        ctk.CTkLabel(card, text="Faça login para acessar o sistema", 
                     text_color="#888780", font=ctk.CTkFont(size=11)).place(relx=0.5, y=100, anchor="n")
        
        # --- 5. CAMPOS DE LOGIN ---
        ctk.CTkLabel(card, text="Login", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w", width=300).place(relx=0.5, y=155, anchor="n")
        
        self._entry_login = ctk.CTkEntry(card, placeholder_text="Informe seu login",
                                         width=300, height=38, corner_radius=6)
        self._entry_login.place(relx=0.5, y=182, anchor="n")
 
        ctk.CTkLabel(card, text="Senha", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w", width=300).place(relx=0.5, y=220, anchor="n")
        
        # Frame auxiliar para agrupar Senha e Botão sem que eles sobreponham as bordas
        frame_senha = ctk.CTkFrame(card, width=300, height=38, fg_color="transparent")
        frame_senha.place(relx=0.5, y=248, anchor="n")
        frame_senha.pack_propagate(False) # Força o frame a manter o tamanho de 300x38

        self._entry_senha = ctk.CTkEntry(frame_senha, placeholder_text="Informe sua senha", show="*", 
                                         width=260, height=38, corner_radius=6)
        self._entry_senha.pack(side="left") # Cola na esquerda
        self._entry_senha.bind("<Return>", lambda e: self._tentar_login())

        self._btn_ver_senha = ctk.CTkButton(frame_senha, text="👁", width=32, height=38,
                                            fg_color="transparent", text_color="#5F5E5A",
                                            hover_color=COR_CINZA_E, font=ctk.CTkFont(size=16),
                                            command=self._alternar_visibilidade_senha)
        self._btn_ver_senha.pack(side="right") # Cola na direita, criando um espaço vazio e seguro no meio!

        # --- 6. MENSAGEM DE ERRO ---
        self._label_erro = ctk.CTkLabel(self, text="", text_color=COR_ERRO,
                                        font=ctk.CTkFont(size=13, weight="bold"), 
                                        wraplength=360, width=360)
        
        # 2. Posicionamento mágico:
        # relx=0.15 : Fica na mesma base lateral do cartão
        # x=180     : Empurra 180px para a direita (alinhando com o centro exato do cartão de 360px)
        # rely=0.5  : Fica na mesma base vertical do cartão
        # y=220     : Empurra para baixo (passando os 208px da metade do cartão, com uma folga de 12px)
        self._label_erro.place( relx=0.775, rely=0.695, anchor="center")

        # --- 7. BOTÃO DE LOGIN ---
        self._btn_login = ctk.CTkButton(card, text="Entrar", width=300, height=40,
                                         fg_color=COR_AZUL_M, hover_color="#1a5276",
                                         font=ctk.CTkFont(size=13, weight="bold"), 
                                         command=self._tentar_login)
        self._btn_login.place(relx=0.5, y=325, anchor="n")
    
    def _tentar_login(self):
        if self._bloqueado:
            return
        
        login= self._entry_login.get().strip()
        senha= self._entry_senha.get()

        if not login or not senha:
            self._mostrar_erro("Preencha ambos os campos para continuar.")
            return
    
        try:
            usuario= AuthService.autenticar(login, senha)
        except Exception as exc:
            self._mostrar_erro(f"Erro ao autenticar: {exc}")
            return

        if usuario is None:
            self._tentativas += 1
            restantes= self.MAX_TENTATIVAS - self._tentativas
            if self._tentativas >= self.MAX_TENTATIVAS:
                self._bloquear()
            else:
                self._mostrar_erro(f"Login ou senha incorretos. Tentativas restantes: {restantes}")
            return
        
        self._mostrar_erro("")
        self._on_sucess(usuario)
    
    
    def _mostrar_erro(self, mensagem):
        self._label_erro.configure(text=mensagem)

    def _bloquear(self):
        self._bloqueado= True
        self._btn_login.configure(state="disabled", text="Bloqueado")
        self._mostrar_erro(
            f"Muitas tentativas incorretas.\n"
            f"Acesso bloqueado por 5 minutos"
        )
        self.after(self.BLOQUEIO_MS, self._desbloquear)

    def _desbloquear(self):
        self._bloqueado= False
        self._tentativas= 0
        self._btn_login.configure(state="normal", text="Entrar")
        self._mostrar_erro("Desbloqueado. Tente novamente.")
    
    def _alternar_visibilidade_senha(self):
        """Alterna a exibição dos caracteres no campo de senha."""
        if self._entry_senha.cget("show") == "*":
            self._entry_senha.configure(show="")
            self._btn_ver_senha.configure(text="🔒")
        else:
            self._entry_senha.configure(show="*")
            self._btn_ver_senha.configure(text="👁")