import logging
import os
import sys
import time
import tkinter as tk
import customtkinter as ctk
import gc
from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu
from customtkinter.windows.widgets.ctk_button import CTkButton
from datetime import datetime

from gui.componentes.tema import (
    COR_AZUL, COR_AZUL_M, COR_SIDEBAR, COR_SIDEBAR_H, COR_SIDEBAR_A,
    COR_PETROLEO, COR_PETROLEO_M, COR_SIDEBAR_PATRIM, COR_SIDEBAR_PATRIM_H, COR_SIDEBAR_PATRIM_A,
    COR_CINZA_E, COR_TEXTO, COR_VERMELHO,
)

logger = logging.getLogger(__name__)


from Modulo_04_notificacoes.scheduler import NotificacaoScheduler
from gui.telas.t01_login import TelaLogin
from tkinter import messagebox
from Modulo_01_autenticacao import SessionManager
from Modulo_05_admin import ConfigService
from gui.componentes.troca_modo import TrocaModoOverlay
from gui.telas.t02_inicio import TelaInicio
from gui.telas.t03_produtos import TelaProdutos
from gui.telas.t21_troca_senha import TelaTrocaSenha
from gui.telas.t05_novo_produto import TelaNovoProduto
from gui.telas.t07_entrada_manual import TelaEntradaManual
#from gui.telas.t08_importar_nfe import TelaImportarNFe
from gui.telas.t07c_entrada_danfe import TelaEntradaDANFE
from gui.telas.t09_retirada import TelaRetirada
from gui.telas.t10_posicao_estoque import TelaPosicaoEstoque
from gui.telas.t22_dashboard import TelaDashboard
from gui.telas.t11_relatorios import TelaCentralRelatorios
from gui.telas.t12_agendamento import TelaAgendamento
from gui.telas.t13_estoque_minimo import TelaEstoqueMinimo
from gui.telas.t15_usuarios import TelaUsuarios
from gui.telas.t17_gmail    import TelaGmail
from gui.telas.t18_backup   import TelaBackup
from gui.telas.t19_log      import TelaLog
from gui.telas.t23_bens_patrimoniais import TelaBensPatrimoniais
from gui.telas.t24_cadastro_bem      import TelaCadastroBem
from gui.telas.t25_movimentacao_baixa import TelaMovimentacaoBaixa

# tema global
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

_original_set_scaling = DropdownMenu._set_scaling

def _safe_set_scaling(self, *args, **kwargs):
    try:
        _original_set_scaling(self, *args, **kwargs)
    except tk.TclError:
        pass # Se o widget for um "fantasma", simplesmente ignora e segue o jogo

DropdownMenu._set_scaling = _safe_set_scaling

_original_button_clicked = CTkButton._clicked

def _safe_button_clicked(self, event=None):
    agora = time.time()
    
    # Inicializa a memória de tempo no botão, se não existir
    if not hasattr(self, '_ultimo_clique'):
        self._ultimo_clique = 0
        
    # COOLDOWN: Se passou menos de 0.5 segundos (500ms) desde o último clique, ele simplesmente ignora!
    if agora - self._ultimo_clique < 0.7:
        return 
        
    # Se passou no teste de tempo, atualiza a memória e executa a função do botão
    self._ultimo_clique = agora
    _original_button_clicked(self, event)

# Injeta a nossa função segura dentro do CustomTkinter
CTkButton._clicked = _safe_button_clicked

class SCEApp(ctk.CTk):
    # Janela raiz do sistema, gerencia login e navegação entre telas
    def __init__(self):
        
        super().__init__()
        if sys.platform.startswith("win"):
            try:
                import ctypes
                myappid = 'uronefrologia.sce.v1.0.1' # Uma string única (ID) para o seu app
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                logger.error("Erro ao definir App ID no Windows: %s", e)

        self.escala_atual = 1.0

        self.title("Sistema de Controle de Estoque - Centro de Uronefrologia")
        self.geometry("1100x600")
        self.minsize(900, 600)

        if sys.platform.startswith("win"):
            self.after(0, lambda: self.state("zoomed"))
        self.configure(fg_color=COR_CINZA_E)

        def aplicar_icone():
            # 1. Mapeamento blindado da pasta raiz
            if getattr(sys, 'frozen', False):
                caminho_raiz = sys._MEIPASS
            else:
                caminho_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                
            caminho_ico = os.path.join(caminho_raiz, "assets", "Logo_Uro_sem_Nome.ico")
            caminho_png = os.path.join(caminho_raiz, "assets", "logo_Centro_Uro_Nefrologia_sem_fundo_sem_letras.png")
            
            try:
                # Tentativa 1: Método nativo do Windows (.ico)
                if os.path.exists(caminho_ico):
                    self.iconbitmap(caminho_ico)
                    self.wm_iconbitmap(caminho_ico)
                
                # Tentativa 2: O Fallback invencível do Tkinter (.png)
                # O CustomTkinter respeita muito mais imagens injetadas via iconphoto
                if os.path.exists(caminho_png):
                    img = tk.PhotoImage(file=caminho_png)
                    self.iconphoto(False, img)
            except Exception as e:
                logger.error("Erro ao forçar o ícone: %s", e)

        # Atrasa a aplicação do ícone para 200ms DEPOIS que o CustomTkinter maximizar a tela
        self.after(200, aplicar_icone)
        # ------------------------------------
        # Estado dee sessão
        self.usuario_logado = None #objeto do usuário logado

        # Estado do subsistema ativo (Estoque/Patrimônio) — ver _alternar_modo.
        self._modo = "estoque"
        self._memoria_tela = {"estoque": "inicio", "patrimonio": "bens_patrimoniais"}
        self._ultimo_destino = "inicio"

        self.bind_all("<Button-1>", self._remover_foco_global)
        self.bind_all("<Control-m>", lambda e: self._alternar_modo())

        self.iniciar_scheduler()
        self.session_timer = None

        #exibe tela de login na inicialização
        self._mostrar_login()

#---- login/ logout ----
    def _mostrar_login(self):
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
        self._mostrar_login()

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
        self._modo = "estoque"

        #corpo: sidebar + main
        self._corpo = ctk.CTkFrame(self, fg_color=COR_CINZA_E)
        self._corpo.grid_columnconfigure(1, weight=1)
        self._corpo.grid_rowconfigure(0, weight=1)

        self._area_conteudo = ctk.CTkFrame(self._corpo, fg_color=COR_CINZA_E)
        self._area_conteudo.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        self._reconstruir_chrome()

        #exibe tela inicial por padrão
        self._navegar(self._memoria_tela[self._modo])

    def _reconstruir_chrome(self):
        """Reconstrói titlebar + sidebar para o modo (Estoque/Patrimônio) atual."""
        if getattr(self, "_titlebar", None):
            self._titlebar.destroy()
        if getattr(self, "_sidebar", None):
            self._sidebar.destroy()
        self._corpo.pack_forget()

        self._titlebar = TitleBar(self, usuario=self.usuario_logado, modo=self._modo)
        self._titlebar.pack(fill="x")

        self._corpo.pack(fill="both", expand=True)

        self._sidebar = Sidebar(
            self._corpo, usuario=self.usuario_logado, on_navigate=self._navegar,
            on_logout=self.logout, modo=self._modo, on_trocar_modo=self._alternar_modo,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsw")

    def _alternar_modo(self):
        """Troca entre os subsistemas Estoque e Patrimônio (Ctrl+M ou botão da sidebar)."""
        if not self.usuario_logado:
            return

        indo_patrimonio = self._modo == "estoque"

        # RF-39/RN-21 — acesso ao Patrimônio exige permissão explícita (TI
        # sempre passa). Ponto único de checagem: cobre tanto o botão da
        # sidebar (que já se oculta sem permissão) quanto o atalho Ctrl+M.
        # Sair do Patrimônio (indo_patrimonio=False) nunca é bloqueado.
        if indo_patrimonio and not self.usuario_logado.pode_acessar_patrimonio:
            return

        self._memoria_tela[self._modo] = self._ultimo_destino
        novo_modo = "patrimonio" if indo_patrimonio else "estoque"

        def trocar():
            self._modo = novo_modo
            self._reconstruir_chrome()
            self._navegar(self._memoria_tela[self._modo])

        try:
            animacao_ligada = ConfigService.get("ui_animacao_transicao") != "0"
        except Exception:
            animacao_ligada = True

        if animacao_ligada:
            overlay = TrocaModoOverlay(self)
            overlay.animar(indo_patrimonio, trocar)
        else:
            trocar()

    def _navegar(self, destino: str):
        """troca o conteudo da area principal pela tela indicada """
        self.resetar_timer_sessao()
        self._ultimo_destino = destino
        self._limpar_area_conteudo()

        tela = self._resolver_tela(destino)
        if tela:
            tela.pack(fill="both", expand=True)
    
    def _resolver_tela(self, destino: str, extra=None):
        """mapeia o indicador de destino para a classe de tela correspondente"""
        nav= self._on_navigate_com_extra
        # sprint 1: telas reia de autenticação plugadas.
        # telas reais colocadas aqui nas proximas sprints
        if destino=="inicio":
            return TelaInicio(self._area_conteudo, usuario=self.usuario_logado, on_navigate= nav)
        
        if destino=="troca_senha":
            return TelaTrocaSenha(self._area_conteudo, usuario=self.usuario_logado, on_navigate= nav)
        
    
        if destino=="produtos":
            return TelaProdutos(self._area_conteudo, usuario= self.usuario_logado, on_navigate= nav)
        
        if destino in("novo_produto", "editar_produto"):
            return TelaNovoProduto(self._area_conteudo, usuario= self.usuario_logado, on_navigate= nav, produto_id= extra)
        
        if destino=="entrada_manual":
            return TelaEntradaManual(self._area_conteudo, usuario= self.usuario_logado, on_navigate= nav, produto_id=extra)
        
        #if destino=="importar_nfe":
        #    return TelaImportarNFe(self._area_conteudo,usuario=self.usuario_logado,on_navigate=nav)
        
        if destino=="entrada_danfe":
            return TelaEntradaDANFE(self._area_conteudo,usuario=self.usuario_logado,on_navigate=nav, produto_id=extra)
        
        if destino == "retirada":
            # Se o extra for um dicionário (veio da T-10)
            if isinstance(extra, dict):
                return TelaRetirada(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav, 
                                    produto_id=extra.get("produto_id"), centro_origem=extra.get("centro_origem"))
            
            # Se for só um número simples (retrocompatibilidade)
            return TelaRetirada(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav, produto_id=extra)
        
        if destino=="baixa_vencido":
            return TelaRetirada(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav, baixa_vencido=True, lotes_vencidos=extra)
        
        if destino=="posicao":
            return TelaPosicaoEstoque(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav, produto_id=extra)
        
        if destino=="dashboard":
            return TelaDashboard(self._area_conteudo,usuario=self.usuario_logado,on_navigate=nav)
        
        if destino=="relatorios":
            return TelaCentralRelatorios(self._area_conteudo,usuario=self.usuario_logado,on_navigate=nav)
        
        if destino=="agendamento":
            return TelaAgendamento(self._area_conteudo,usuario= self.usuario_logado, on_navigate= nav)
        
        if destino=="estoque_minimo":
            return TelaEstoqueMinimo(self._area_conteudo, usuario=self.usuario_logado, on_navigate= nav)
        
        if destino == "usuarios":
            return TelaUsuarios(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav)
        
        if destino == "gmail":
            return TelaGmail(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav)
        
        if destino == "backup":
            return TelaBackup(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav)
        
        if destino == "log":
            return TelaLog(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav)

        # MOD-07 — Patrimônio
        if destino == "bens_patrimoniais":
            return TelaBensPatrimoniais(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav)

        if destino in ("novo_bem", "editar_bem"):
            return TelaCadastroBem(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav, bem_id=extra)

        if destino == "movimentar_bem":
            return TelaMovimentacaoBaixa(self._area_conteudo, usuario=self.usuario_logado, on_navigate=nav, bem_id=extra)

    def _on_navigate_com_extra(self, destino: str, extra=None):
        """Versão do _navegar que aceita parâmetro extra(ex: produto_id)"""
        self.resetar_timer_sessao()
        self._ultimo_destino = destino
        self._limpar_area_conteudo()
        tela= self._resolver_tela(destino, extra= extra)
        if tela:
            tela.pack(fill="both", expand= True)

    def ajustar_zoom(self, incremento):
        """Aumenta ou diminui o tamanho de todas as fontes e componentes do sistema"""
        nova_escala = self.escala_atual + incremento
        
        # Limites de segurança para a interface não explodir na tela nem ficar minúscula
        if 0.8 <= nova_escala <= 1.4: 
            self.escala_atual = nova_escala
            
            # Aplica o zoom nos textos e widgets
            ctk.set_widget_scaling(self.escala_atual)
            
            # (Opcional) Se quiser que a janela inteira cresça junto
            # ctk.set_window_scaling(self.escala_atual)

    def destroy(self):
       self._scheduler.parar()
       super().destroy()
    
    def iniciar_scheduler(self):
        #Inicializa o scheduler de notificações
        self._scheduler= NotificacaoScheduler()
        self._scheduler.iniciar()

    def parar_scheduler(self):
        self._scheduler.parar()
    
    def _limpar_area_conteudo(self):
        """Destrói os widgets e força o Python a liberar a memória RAM retida."""
        for w in self._area_conteudo.winfo_children():
            # 1. Tenta limpar grandes volumes de dados se a tela tiver esse recurso
            if hasattr(w, 'limpar_memoria'):
                try:
                    w.limpar_memoria()
                except Exception as e:
                    logger.error("Erro ao limpar memória da tela: %s", e)
            
            # 2. Destrói o widget visualmente
            w.destroy()
            
            # 3. Remove a referência local
            del w 
            
        # 4. Força o Coletor de Lixo do Python a passar e esvaziar a RAM imediatamente
        gc.collect()
    
    def _remover_foco_global(self, event):
        """Remove o cursor do campo de texto ao clicar no fundo ou em outros elementos."""
        try:
            # O CustomTkinter é feito de várias camadas. Precisamos saber a classe base do item clicado
            classe_widget = event.widget.winfo_class()
            
            # "Entry" é o input de uma linha, "Text" é o input de múltiplas linhas
            # Se o usuário clicou em algo que não seja um input (ex: no fundo cinza, num Label, etc)
            if classe_widget not in ("Entry", "Text"):
                # Nós mandamos a janela principal (o fundo) assumir o controle do teclado
                self.focus_set()
        except Exception:
            pass # Ignora erros caso o widget clicado já tenha sido destruído
       
#---- Componentes da janela principal (titlebar, sidebar) --------------------------------------------------------------

class TitleBar(ctk.CTkFrame):
    """Barra de titulo superior- CP-01"""

    def __init__(self, master, usuario, modo: str = "estoque"):
        cor_fundo = COR_PETROLEO if modo == "patrimonio" else COR_AZUL
        texto_titulo = ("Sistema de Controle de Patrimônio - Centro de Uro-nefrologia" if modo == "patrimonio"
                        else "Sistema de Controle de Estoque - Centro de Uro-nefrologia")
        super().__init__(master, fg_color=cor_fundo, height=36, corner_radius=0)
        self.pack_propagate(False)

        ctk.CTkLabel(
            self, text= texto_titulo,
            text_color="white", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=8)

        #Informações do usuário e botão de logout
        frame_direita = ctk.CTkFrame(self, fg_color="transparent")
        frame_direita.pack(side="right", padx=12)

        # Exemplo de botões (podem ser colocados na sua barra de menu)
        frame_zoom = ctk.CTkFrame(self, fg_color="transparent")
        frame_zoom.pack(side="right", padx=16)


        # Botão Aumentar (A+)
        ctk.CTkButton(frame_zoom, text="A+", width=30, height=28,
                      command=lambda: self.winfo_toplevel().ajustar_zoom(0.1)).pack(side="left", padx=2)
                      
        # Botão Diminuir (A-)
        ctk.CTkButton(frame_zoom, text="A-", width=27, height=25,
                      command=lambda: self.winfo_toplevel().ajustar_zoom(-0.1)).pack(side="left", padx=2)


        hora= datetime.now().strftime("| %d/%m/%Y %H:%M")
        nome_perfil= f"({usuario.perfil.value.capitalize()}): {usuario.nome} "
        ctk.CTkLabel(                   
            frame_direita,
            text= f"{nome_perfil} . {hora}",
            text_color="white", font=ctk.CTkFont(size=11)
        ).pack(side="left")
    
class Sidebar(ctk.CTkFrame):
    """Menu lateral com itens por perfil - CP-02"""
    MENU_ESTOQUE = [
        ("__label__"        ,"Estoque",                       None),
        ("inicio"           ,"Início",                        ["tecnico", "admin","ti"]),
        ("produtos"         ,"Produtos",                      ["ti", "tecnico", "admin"]),
        ("__label__"        ,"Movimentações",                 None),
        ("entrada_manual"   ,"Entrada Manual",                ["admin", "tecnico", "ti"]),
        ("importar_nfe"     ,"Importar NF-e",                 []),
        ("entrada_danfe"    ,"Entrada DANFE",                 ["admin", "tecnico", "ti"]),
        ("retirada"         ,"Retirada/ Transferencia",       ["admin", "tecnico", "ti"]),
        ("__label__"        ,"Consulta",                      None),
        ("posicao"          ,"Posição de Estoque",            ["admin", "tecnico", "ti"]),
        ("dashboard"        ,"Dashboard",                     ["admin", "ti"]),
        ("__label__"        ,"Relatórios",                    None),
        ("relatorios"       ,"Gerar Relatórios",              ["admin", "ti"]),
        ("agendamento"      ,"Agendamento",                   ["ti", "admin"]),
        ("estoque_minimo"   ,"Estoque Mínimo" ,               ["admin", "ti"]),
        ("__label__"        ,"Configurações",                 None),
        ("usuarios"         ,"Gerenciamento de Usuários" ,    ["ti"]),
        ("gmail"            ,"Configurações Gmail" ,          ["ti"]),
        ("backup"           ,"Backup do Sistema" ,            ["ti"]),
        ("log"              ,"Log de Operações" ,             ["ti"]),
    ]

    # MOD-07 — Sprint 9 só entrega T-23/T-24; T-25 é aberta a partir de T-23
    # ("Abrir" na linha do bem, com bem_id), não por item de menu próprio.
    # Etiquetas/Localizações/Configurações ficam de fora do menu até terem
    # tela (S10/S11) — mesmo padrão já usado aqui para "Importar NF-e".
    MENU_PATRIMONIO = [
        ("__label__"          ,"Bens",              None),
        ("bens_patrimoniais"  ,"Bens patrimoniais", ["tecnico", "admin", "ti"]),
        ("novo_bem"           ,"Cadastrar bem",      ["tecnico", "admin", "ti"]),
    ]

    def __init__(self, master, usuario, on_navigate, on_logout, modo: str = "estoque", on_trocar_modo=None):
        self._modo = modo
        cor_fundo = COR_SIDEBAR_PATRIM if modo == "patrimonio" else COR_SIDEBAR
        super().__init__(master, fg_color=cor_fundo, width=200,corner_radius=0)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._usuario=usuario
        self._perfil = usuario.perfil.value
        self._botoes = {}
        self._ativo= None
        self._on_logout= on_logout
        self._on_trocar_modo = on_trocar_modo
        self._menu = self.MENU_PATRIMONIO if modo == "patrimonio" else self.MENU_ESTOQUE
        self._cor_hover = COR_SIDEBAR_PATRIM_H if modo == "patrimonio" else COR_SIDEBAR_H
        self._cor_ativo = COR_SIDEBAR_PATRIM_A if modo == "patrimonio" else COR_SIDEBAR_A
        self._construir()

    def _construir(self):
        nome_perfil= f" {self._usuario.nome} "
        usuario_perfil=f"{self._usuario.perfil.value.capitalize()}"
        frame_perfil=ctk.CTkFrame(self, fg_color="transparent")
        frame_perfil.pack(fill="x", padx=14,pady=(10,5), side="top")
        ctk.CTkLabel(                   
            frame_perfil,
            text= f"{nome_perfil}",
            text_color="white", font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        ).pack(anchor="w", pady=(0,2))

        badge_perfil=ctk.CTkFrame(frame_perfil, fg_color="#3A5B7C", 
                                  corner_radius=10)
        badge_perfil.pack(anchor="w")

        ctk.CTkLabel(badge_perfil, text=usuario_perfil,
                     text_color="#B3D4F0", font=ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(padx=10, pady=2)

        #linha separadora 
        ctk.CTkFrame(self, fg_color="#111111", height=1).pack(fill="x", padx=14, pady=(12, 10), side="top")

        #Menu de navegação
        self._menu_scroll = ctk.CTkScrollableFrame(
        self, 
        fg_color="transparent", 
        corner_radius=0,
        label_text="" 
        )
        self._menu_scroll.pack(fill="both", expand=True, side="top")

        label_pendente= None
        for item in self._menu:
            destino, label, perfis = item

            if destino == "__label__":
                label_pendente=label    
                continue

            permitido= perfis and self._perfil in perfis
            if permitido:
                if label_pendente:
                    ctk.CTkLabel(
                        self._menu_scroll, 
                        text=label_pendente.upper(),
                        text_color="#7fa8cc",
                        font=ctk.CTkFont(size=9, weight="bold"),
                        anchor="w",
                    ).pack(fill="x", padx=14, pady=(10, 2))

                    label_pendente = None
                btn = ctk.CTkButton(
                    self._menu_scroll,
                    text=f"  {label}",
                    anchor="w",
                    fg_color="transparent",
                    text_color="white",
                    hover_color=self._cor_hover,
                    height=32,
                    corner_radius=6,
                    font=ctk.CTkFont(size=12),
                    state="normal",
                    command=lambda d=destino: self._clicar(d)
                )
                btn.pack(fill="x", padx=6, pady=1)
                self._botoes[destino] = btn

        frame_rodape= ctk.CTkFrame(self, fg_color="transparent")
        frame_rodape.pack(fill="x", padx=14, pady=16, side="bottom")
        frame_rodape.grid_columnconfigure((0,1), weight=1)

        #botão troca senha
        btn_senha= ctk.CTkButton(frame_rodape, text="Trocar senha",
                                 fg_color="transparent", text_color="#888780", height=30,
                                 font=ctk.CTkFont(size=11),
                                 command=lambda:self._on_navigate("troca_senha"))
        btn_senha.grid(row=0,column=0, padx=(0,4), sticky="ew")

        #botão sair
        btn_sair= ctk.CTkButton(
            frame_rodape, text="Sair",width=50, height=24,
            fg_color="transparent",text_color="#888780",
            font=ctk.CTkFont(size=11, weight="bold"),command=self._on_logout
        )
        btn_sair.grid(row=0,column=1,padx=(4,0), sticky="ew")

        # Botão de troca de subsistema — acima de "Trocar senha · Sair",
        # separado por borda superior (packed depois, side="bottom" empilha
        # por cima do que já foi packed no rodapé).
        # RF-39/RN-21 — entrar no Patrimônio exige permissão explícita (TI
        # sempre tem); voltar ao Estoque nunca é bloqueado.
        mostrar_botao_modo = self._modo == "patrimonio" or self._usuario.pode_acessar_patrimonio
        if self._on_trocar_modo and mostrar_botao_modo:
            texto_troca = "‹ Voltar ao Estoque" if self._modo == "patrimonio" else "Ir para Patrimônio  ›"
            btn_modo = ctk.CTkButton(
                self, text=texto_troca, anchor="w",
                fg_color=self._cor_hover, hover_color=self._cor_ativo,
                text_color="white", height=38, corner_radius=0,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self._on_trocar_modo,
            )
            btn_modo.pack(fill="x", side="bottom")

    def _clicar(self, destino: str):
        # Remove destaque anterior
        if self._ativo and self._ativo in self._botoes:
            self._botoes[self._ativo].configure(fg_color="transparent")
        # Destaca ativo
        self._ativo = destino
        self._botoes[destino].configure(fg_color=self._cor_ativo)
        self._on_navigate(destino)


