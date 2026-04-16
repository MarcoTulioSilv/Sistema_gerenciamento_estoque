"""
gui. telas . t01_login.py
tela T-01 - login
Sprint 1 implementará o AuthenService real.
Srint 0: estrutura visual completa, autenticação integrada com MOD-01.
"""
import customtkinter as ctk
from typing import Callable

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_AZUL_L = "#D6E4F0"
COR_ERRO   = "#A32D2D"
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
        #Centraliza o card
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card= ctk.CTkFrame(self, width=360, fg_color="white",
                            corner_radius=12, border_width=1, border_color="#D3D1C7")
        card.grid(row=0, column=0, padx=20, pady=20)
        card.grid_propagate(False)
        card.configure(height= 460)

        #Logo/ cabeçalho
        logo_frame= ctk.CTkFrame(card, fg_color=COR_AZUL, width=52, height=52, corner_radius=10)
        logo_frame.place(relx=0.5, y=44, anchor="center")

        ctk.CTkLabel(card, text="SCE Centro de Uro-Nefrologia", text_color= COR_AZUL,
                    font= ctk.CTkFont(size=20, weight="bold")).place(relx=0.5, y=104, anchor="center")
        ctk.CTkLabel(card, text= "Faça login para acessar o sistema", 
                     text_color="#888780", font= ctk.CTkFont(size=11)).place(relx=0.5, y=126, anchor="center")
        
        #campos de login
        ctk.CTkLabel(card, text="Login", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w",width=300).place(x=30, y=158)
        self._entry_login = ctk.CTkEntry(card, placeholder_text="Informe seu login",
                                          width=300, height=38, corner_radius=6)
        self._entry_login.place(x=30, y=176)
 
        ctk.CTkLabel(card, text="Senha", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w", width=300).place(x=30, y=224)
        self._entry_senha = ctk.CTkEntry(card, placeholder_text="Informe sua senha",
                                          show="*", width=300, height=38, corner_radius=6)
        self._entry_senha.place(x=30, y=242)
        self._entry_senha.bind("<Return>", lambda e: self._tentar_login())

        #Mensagem de erro
        self._label_erro = ctk.CTkLabel(card, text="", text_color=COR_ERRO,
                                        font=ctk.CTkFont(size=11), wraplength=300, width=300)
        self._label_erro.place(x=30, y=290)

        #Botão de login
        self._btn_login = ctk.CTkButton(card, text="Entrar",width=300, height=40,
                                         fg_color=COR_AZUL_M, hover_color="#1a5276",
                                         font= ctk.CTkFont(size=13,weight="bold"), 
                                         command=self._tentar_login)
        self._btn_login.place(x=30, y=316)

        ctk.CTkLabel(card, text="Em caso de dificuldades, contate o suporte técnico.",
                      text_color="#AAAAAA",font=ctk.CTkFont(size=10)).place(relx=0.5, y=374, anchor="center")
        
        self._entry_login.focus()
    
    def _tentar_login(self):
        if self._bloqueado:
            return
        
        login= self._entry_login.get().strip()
        senha= self._entry_senha.get()

        if not login or not senha:
            self._mostrar_erro("Preencha ambos os campos para continuar.")
            return
        
        #Delega autenticação ao MOD-01
        #Sprint 0: importa diretamente para teste de estrutura
        try:
            from Modulo_01_autenticacao import AuthService
            usuario= AuthService.autenticar(login, senha)
        except ImportError:
            # Sprint 0: MOD-01 não implementado, adimin/adimin
            usuario= self._login_stub(login, senha)
        except Exception as exc:
            self._exibir_erro(f"Erro ao autenticar: {exc}")
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
    
    def _login_stub(self, login, senha):
        """ Stub de autenticação para sprint 0- aceita adimin/adimin para perminir testar a janela prinicipal"""
        if login == "admin" and senha == "admin":
            #cria objeto minimo que a gui precisa
            class UsuarioStub:
                id = 1
                nome = "Administrador"
                login= "admin"
                class perfil:
                    value= "ti"
            return UsuarioStub()
        return None
    
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
        