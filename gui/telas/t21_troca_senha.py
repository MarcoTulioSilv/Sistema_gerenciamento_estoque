"""
gui . telas . t21_troca_senha.py
Tela T21- Troca de senha- todos os perfis
Sprint 1: inetegra com AuthService(verificação bcrypt+ gravação no banco)
"""
import logging
import customtkinter as ctk
from tkinter import messagebox
from Modulo_01_autenticacao import AuthService
from Modulo_06_dados import get_session, Usuario

logger= logging.getLogger(__name__)

COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_E= "#F2F1ED"
COR_CINZA_B= "#E8E6DE"
COR_ERRO   = "#A32D2D"
COR_BRANCO = "#FFFFFF"

class TelaTrocaSenha(ctk.CTkFrame):
    """ Tela de troca de senha- UC-09 parcial(qualquer perfil popde trocar a própria senha)."""

    def __init__(self, master, usuario):
        super().__init__(master,fg_color=COR_CINZA_E,corner_radius=0)
        self._usuario= usuario
        self._construir()
    
    def _construir(self):
        #topbar
        topbar = ctk.CTkFrame(self, fg_color=COR_BRANCO, height=44, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Trocar minha senha",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(side="left", padx=16, pady=10)
        #Card central
        card = ctk.CTkFrame(self, fg_color=COR_BRANCO, corner_radius=10,
                             border_width=1, border_color=COR_CINZA_B, width=440)
        card.pack(pady=32, padx=32, anchor="nw")

        ctk.CTkLabel(card, text="Alteração de senha",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkFrame(card, fg_color=COR_CINZA_B, height=1).pack(fill="x", padx=16, pady=(8, 14))

        # Campos
        def campo(parent, label, show=""):
            ctk.CTkLabel(parent, text=label, text_color="#5F5E5A",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         anchor="w").pack(fill="x", padx=16, pady=(0, 3))
            entry = ctk.CTkEntry(parent, show=show, width=400, height=36, corner_radius=6)
            entry.pack(padx=16, pady=(0, 12))
            return entry
        self._entry_atual = campo(card,"Senha atual *", show="*")
        self._entry_nova = campo(card,"Nova senha *", show="*")
        self._entry_conf= campo(card,"Confirmar nova senha *", show="*")

        ctk.CTkLabel(card, text="Mínimo 8 caracteres.",
                     text_color="#AAAAAA",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16)
        
        #Mensagem de feedback
        self._lbl_msg=ctk.CTkLabel(card, text="",text_color=COR_ERRO,
                                   font=ctk.CTkFont(size=11),wraplength=400)
        self._lbl_msg.pack(padx=15, pady=(8,0))
        
        #botões
        row_btns= ctk.CTkFrame(card,fg_color="transparent")
        row_btns.pack(anchor="e", padx=16, pady=14)
        ctk.CTkButton(row_btns,text="Cancelar", width=100, height=34,
                      fg_color=COR_BRANCO, text_color="#3d3d3a",
                      border_width=1, border_color= COR_CINZA_B,
                      hover_color=COR_CINZA_E,
                      command=self._cancelar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_btns, text="Salvar nova senha", width=160, height=34,
                      fg_color=COR_AZUL_M, hover_color="#1a5276",
                      command=self._salvar).pack(side="left")
    
    def _salvar(self):
        atual   = self._entry_atual.get()
        nova    = self._entry_nova.get()
        conf    = self._entry_conf.get()

        # Validações locais
        if not atual  or not nova or not conf:
            self._msg("Preencha todos os campos.", erro=True)
            return
        if len(nova)<8:
            self._msg("A nova senha deve ter no minimo 8 digitos.", erro=True)
            return
        if nova != conf:
            self._msg("Nova senha e confirmação não coincidem.", erro=True)
            return
        if nova == atual:
            self._msg("A nova senha deve ser diferente da atual.", erro=True)
            return
        
        # Verifica senha atual e grava nova
        try:
            # Verifica senha atual
            if not AuthService.verificar_senha(atual,self._usuario.senha_hash):
                self._msg("Senha atual incorreta.", erro=True)
                return
            
            #grava nova senha 
            novo_hash= AuthService.hash_senha(nova)
            with get_session() as session:
                usuario_db= session.get(Usuario, self._usuario.id)
                if usuario_db:
                    usuario_db.senha_hash= novo_hash
                    # Atualiza o objeto em mémoria também
                    self._usuario.senha_hash= novo_hash
            
            logger.info("Senha alterada com sucesso: pelo usuario %s", self._usuario.login)
            self._msg("", erro=False)
            messagebox.showinfo("Senha alterada", "Sua senha foi alterada com sucesso.")
            self._limpar()
        except Exception as exc:
            logger.error("Erro ao alterar senha: %s", exc)
            self._msg(f"Erro ao alterar senha:{exc}", erro=True)
    
    def _cancelar(self):
        self.limpar()
    
    def _limpar(self):
        self._entry_atual.delete(0,"end")
        self._entry_nova.delete(0,"end")
        self._entry_conf.delete(0,"end")
        self._msg("")
    
    def _msg(self, texto: str,erro:bool=True):
        cor= COR_ERRO if erro else "#1D9E75"
        self._lbl_msg.configure(text=texto, text_color= cor)