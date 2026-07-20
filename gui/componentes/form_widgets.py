"""
gui . componentes. form_widgets.py
Widgets de formulário reutilizaveis- CP-03, CP-04, CP-05 do guia de componentes
Usados em T-05, T-06, T07 e demais telas de cadastro.
"""
import customtkinter as ctk
import tkinter as tk
from Modulo_02_estoque import EstoqueService
import logging

logger= logging.getLogger(__name__)
COR_AZUL   = "#1F4E79"
COR_AZUL_M = "#2E75B6"
COR_CINZA_B= "#E8E6DE"
COR_CINZA_E= "#F2F1ED"
COR_ERRO   = "#A32D2D"
COR_BRANCO = "#FFFFFF"
COR_VERDE  = "#1D9E75"

class Campo(ctk.CTkFrame):
    """
    Campo de formulário com label, entry/select e mensagem de erro- CP-03.
    obrigatório = True adiciona ao label.
    """

    def __init__( self, master, label:str, obrigatorio: bool=False,
                 tipo: str="entry", opcoes: list=None,
                 placeholder:str="", largura: int=300, **kwargs):
        super().__init__(master, fg_color="transparent",**kwargs)
        self._obrigatorio= obrigatorio
        self._tipo= tipo

        #Label
        txt=f"{label}*" if obrigatorio else label 
        ctk.CTkLabel(self, text= txt, text_color="#5F5E5A",
                     font= ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(fill="x",pady=(0,3))
        
        #Wiget de entrada
        if tipo =="entry":
            self._widget= ctk.CTkEntry(
                self, placeholder_text= placeholder, 
                width=largura, height= 34, corner_radius=6,
            )
        elif tipo == "select":
            self._widget= ctk.CTkOptionMenu(
                self, values= opcoes or [],
                width= largura, height= 34, corner_radius=6,
                fg_color=COR_CINZA_E, button_color= COR_AZUL_M,
                text_color="#3d3d3a",
            )
        elif tipo == "number":
            self._widget= ctk.CTkEntry(
                self, placeholder_text= placeholder or "0", 
                width= largura, height= 34, corner_radius= 6,
            )
        self._widget.pack(fill="x")

        #Mensagem de erro( oculta por padrão)
        self._lbl_erro= ctk.CTkLabel(
            self, text="", text_color=COR_ERRO,
            font=ctk.CTkFont(size=10), anchor="w",
        )
        self._lbl_erro.pack(fill="x")
    
    def get(self)-> str:
        if self._tipo=="select":
            return self._widget.get()
        return self._widget.get().strip()
    

    def set(self, valor: str):
        if self._tipo== "select":
            self._widget.set(valor)
        else:
            self._widget.delete(0,"end")
            self._widget.insert(0,str(valor))
    
    def erro(self, mensagem: str=""):
        self._lbl_erro.configure(text=mensagem)
        cor="#F09595" if mensagem else COR_CINZA_B
        try:
            self._widget.configure(border_color=cor)
        except Exception:
            pass
    
    def limpar(self):
        self.erro("")
        if self._tipo == "select":
            pass
        else:
            self._widget.delete(0,"end")
    
    def validar(self)-> bool:
        #Valida campo obrigatório. Retorna True se válido.
        if self._obrigatorio and not self.get():
            self.erro("Campo obrigatório")
            return False 
        self.erro("")
        return True

    def focus(self): 
        self._widget.focus()


class CampoBarras(ctk.CTkFrame):
    """
    Campo de codigo de barras com tag HID USB- CP-04.
    on_leitura: callback chamado quando usuário preenche o campo e pressiona enter
    """

    def __init__(self, master, label:str="Código de barras(EAN)", obrigatorio: bool=True,
                 on_leitura=None, largura: int=300, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._obrigatorio= obrigatorio
        self._on_leitura= on_leitura

        ctk.CTkLabel(self, text=f"{label}*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(fill="x", pady=(0,3))
        
        row= ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")

        self._entry= ctk.CTkEntry(
            row, placeholder_text="Leia o código ou digite o EAN",
            height=34, corner_radius=6,
        )
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.bind("<Return>", self._disparar)
        self._entry.bind("<FocusOut>", self._disparar)

        ctk.CTkLabel(row, text="HIB USB", fg_color=COR_AZUL_M,
                     text_color="white", corner_radius=5, 
                     font=ctk.CTkFont(size=10, weight="bold"),
                     padx=8, pady=4).pack(side="left", padx=(6,0))
        
        self._lbl_erro= ctk.CTkLabel(
            self, text="", text_color=COR_ERRO,
            font=ctk.CTkFont(size=10), anchor="w",
        )
        self._lbl_erro.pack(fill="x")

    def get(self)-> str:
        return self._entry.get().strip()
    
    def set(self, valor:str):
        self._entry.delete(0,"end")
        self._entry.insert(0,valor)

    def erro(self, mensagem: str=""):
        self._lbl_erro.configure(text=mensagem)
    
    def limpar(self):
        self._entry.delete(0,"end")
        self.erro("")
    
    def validar(self)-> bool:
        if self._obrigatorio and not self.get():
            self.erro("Campo obrigatório")
            return False
        self.erro("")
        return True

    def focus(self):
        self._entry.focus()
    
    def _disparar(self, _event=None):
        if self._on_leitura and self.get():
            self._on_leitura(self.get())
            
class CampoNome(ctk.CTkFrame):
    """
    Campo com Autocompletar Real (Inline Expansion).
    A lista aparece sozinha durante a digitação e empurra os componentes abaixo.
    """

    def __init__(self, master, label:str="Nome do Produto", obrigatorio: bool=True,
                 on_leitura=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._obrigatorio = obrigatorio
        self._on_leitura = on_leitura
        self._todas_sugestoes = []
        self._sugestoes_atuais=[]

        ctk.CTkLabel(self, text=f"{label}*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(fill="x", pady=(0,3))
        
        self._row = ctk.CTkFrame(self, fg_color="transparent")
        self._row.pack(fill="x")

        self._entry = ctk.CTkEntry(
            self._row, placeholder_text="Digite para buscar...",
            height=34, corner_radius=6,
            fg_color=COR_CINZA_E, text_color="#3d3d3a"
        )
        self._entry.pack(side="left", fill="x", expand=True)

        self._listbox = tk.Listbox(
            self, bg=COR_CINZA_E, fg="#3d3d3a",
            selectbackground=COR_AZUL_M, selectforeground="white",
            relief="flat", borderwidth=1, highlightthickness=1, highlightcolor=COR_CINZA_B,
            font=ctk.CTkFont(size= 11, weight="bold")
        )

        self._lbl_erro = ctk.CTkLabel(
            self, text="", text_color=COR_ERRO,
            font=ctk.CTkFont(size=10), anchor="w",
        )
        self._lbl_erro.pack(fill="x")

        # 3. Eventos que controlam o autocompletar
        self._entry.bind("<KeyRelease>", self._filtrar_sugestoes)
        self._entry.bind("<Return>", self._ao_pressionar_enter)
        self._entry.bind("<Down>", self._navegar_baixo)
        self._entry.bind("<Up>", self._navegar_cima)
        self._entry.bind("<Escape>", lambda e: self._esconder_lista())
        self._entry.bind("<FocusOut>", self._esconder_lista_delay)
        self._listbox.bind("<<ListboxSelect>>", self._selecionar_item)
        self._listbox.bind("<ButtonRelease-1>", self._selecionar_item)

        self._carregar_sugestoes_nome()

    def get(self) -> str:
        return self._entry.get().strip()
    
    def set(self, valor:str):
        self._entry.delete(0, "end")
        self._entry.insert(0, valor)

    def erro(self, mensagem: str=""):
        self._lbl_erro.configure(text=mensagem)
    
    def limpar(self):
        self._entry.delete(0, "end")
        self._esconder_lista()
        self.erro("")
    
    def validar(self) -> bool:
        if self._obrigatorio and not self.get():
            self.erro("Campo obrigatório")
            return False
        self.erro("")
        return True

    def focus(self):
        self._entry.focus()
    
    def _disparar(self, _event=None):
        if self._on_leitura and self.get():
            self._esconder_lista()
            self._on_leitura(self.get())

    def _carregar_sugestoes_nome(self):
        try:
            self._todas_sugestoes = EstoqueService.listar_nomes_unicos()
        except Exception as exc:
            logger.warning("Erro ao carregar sugestões de nomes: %s", exc)

    # ── Lógica do Autocompletar ──────────────────────────────────────────────

    def _filtrar_sugestoes(self, event=None):
        # Ignora teclas de navegação para não bugar a digitação
        if event and event.keysym in ("Down", "Up", "Return", "Escape", "Left", "Right"):
            return

        texto_digitado = self.get().lower()
        
        # Se apagou tudo, esconde a lista
        if not texto_digitado:
            self._esconder_lista()
            return

        self._sugestoes_atuais = [s for s in self._todas_sugestoes if texto_digitado in s.lower()]

        if self._sugestoes_atuais:
            self._listbox.delete(0, tk.END)
            for item in self._sugestoes_atuais[:8]:
                self._listbox.insert(tk.END, item)     
            # Insere a lista VISUALMENTE logo abaixo do entry (antes da msg de erro)
            self._listbox.pack(fill="x", after=self._row, pady=(2, 0))
        else:
            self._esconder_lista()
        
    def _navegar_baixo(self, event=None):
        """Move a seleção da lista para o item de baixo."""
        if not self._listbox.winfo_ismapped() or not self._sugestoes_atuais:
            return "break" # Evita que a seta mova o cursor de texto na Entry
        
        selecionados = self._listbox.curselection()
        if not selecionados:
            proximo_idx = 0
        else:
            proximo_idx = min(selecionados[0] + 1, self._listbox.size() - 1)
            self._listbox.selection_clear(0, tk.END)
        
        self._listbox.selection_set(proximo_idx)
        self._listbox.activate(proximo_idx)
        self._listbox.see(proximo_idx)
        return "break"
    
    def _navegar_cima(self, event=None):
        """Move a seleção da lista para o item de cima."""
        if not self._listbox.winfo_ismapped() or not self._sugestoes_atuais:
            return "break"
        
        selecionados = self._listbox.curselection()
        if not selecionados or selecionados[0] == 0:
            # Se já está no topo ou sem seleção, remove a seleção
            self._listbox.selection_clear(0, tk.END)
            return "break"
        
        anterior_idx = selecionados[0] - 1
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(anterior_idx)
        self._listbox.activate(anterior_idx)
        self._listbox.see(anterior_idx)
        return "break"
    
    def _ao_pressionar_enter(self, event=None):
        """
        Confirma a sugestão selecionada (se a lista estiver visível e com foco em um item),
        ou dispara a busca final caso nenhuma sugestão esteja selecionada.
        """
        if self._listbox.winfo_ismapped():
            selecionados = self._listbox.curselection()
            if selecionados:
                # Se tem sugestão selecionada, completa o texto!
                texto_escolhido = self._listbox.get(selecionados[0])
                self.set(texto_escolhido)
                self._esconder_lista()
                # Posiciona o cursor de texto no final do nome inserido
                self._entry.icursor(tk.END)
                return "break"
        
        # Se não escolheu nada na lista ou já escondeu, dispara a busca (on_leitura)
        self._disparar()

    def _selecionar_item(self, event=None):
        selecionados = self._listbox.curselection()
        if selecionados:
            texto_escolhido = self._listbox.get(selecionados[0])
            self.set(texto_escolhido)
            self._esconder_lista()
            self._entry.focus()
            self._entry.icursor(tk.END)
            self._disparar()

    def _esconder_lista(self):
        if self._listbox.winfo_ismapped():
            self._listbox.pack_forget()
            self._listbox.selection_clear(0, tk.END)

    def _esconder_lista_delay(self, event=None):
        self.after(200, self._esconder_lista)

class CampoFornecedor(ctk.CTkFrame):
    """
    Campo com Autocompletar Real (Inline Expansion).
    A lista aparece sozinha durante a digitação e empurra os componentes abaixo.
    """

    def __init__(self, master, label:str="Nome do Fornecedor", obrigatorio: bool=True,
                 on_leitura=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._obrigatorio = obrigatorio
        self._on_leitura = on_leitura
        self._todas_sugestoes = []

        ctk.CTkLabel(self, text=f"{label}*", text_color="#5F5E5A",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(fill="x", pady=(0,3))
        
        self._row = ctk.CTkFrame(self, fg_color="transparent")
        self._row.pack(fill="x")

        self._entry = ctk.CTkEntry(
            self._row, placeholder_text="Digite para buscar ou cadastrar um fornecedor",
            height=34, corner_radius=6,
            fg_color=COR_CINZA_E, text_color="#3d3d3a"
        )
        self._entry.pack(side="left", fill="x", expand=True)

        self._listbox = tk.Listbox(
            self, bg=COR_CINZA_E, fg="#3d3d3a",
            selectbackground=COR_AZUL_M, selectforeground="white",
            relief="flat", borderwidth=1, highlightthickness=1, highlightcolor=COR_CINZA_B,
            font=ctk.CTkFont(size= 11, weight="bold")
        )

        self._lbl_erro = ctk.CTkLabel(
            self, text="", text_color=COR_ERRO,
            font=ctk.CTkFont(size=10), anchor="w",
        )
        self._lbl_erro.pack(fill="x")

        # 3. Eventos que controlam o autocompletar
        self._entry.bind("<KeyRelease>", self._filtrar_sugestoes)
        self._entry.bind("<Return>", self._disparar)
        self._entry.bind("<FocusOut>", self._esconder_lista_delay)
        self._listbox.bind("<<ListboxSelect>>", self._selecionar_item)

        self._carregar_sugestoes_nome()

    def get(self) -> str:
        return self._entry.get().strip()
    
    def set(self, valor:str):
        self._entry.delete(0, "end")
        self._entry.insert(0, valor)

    def erro(self, mensagem: str=""):
        self._lbl_erro.configure(text=mensagem)
    
    def limpar(self):
        self._entry.delete(0, "end")
        self._esconder_lista()
        self.erro("")
    
    def validar(self) -> bool:
        if self._obrigatorio and not self.get():
            self.erro("Campo obrigatório")
            return False
        self.erro("")
        return True

    def focus(self):
        self._entry.focus()
    
    def _disparar(self, _event=None):
        if self._on_leitura and self.get():
            self._esconder_lista()
            self._on_leitura(self.get())

    def _carregar_sugestoes_nome(self):
        try:
            self._todas_sugestoes = EstoqueService.listar_fornecedores_unicos()
        except Exception as exc:
            logger.warning("Erro ao carregar sugestões de nomes: %s", exc)

    # ── Lógica do Autocompletar ──────────────────────────────────────────────

    def _filtrar_sugestoes(self, event):
        # Ignora teclas de navegação para não bugar a digitação
        #if event.keysym in ("Return", "Down", "Up", "Tab", "Escape"):
         #   return

        texto_digitado = self.get().lower()
        
        # Se apagou tudo, esconde a lista
        if not texto_digitado:
            self._esconder_lista()
            return

        filtrados = [s for s in self._todas_sugestoes if texto_digitado in s.lower()]

        if filtrados:
            self._listbox.delete(0, tk.END)
            for item in filtrados:
                self._listbox.insert(tk.END, item)

            # Limita o tamanho da lista para não tomar a tela toda (máx 5 itens)
            altura = min(len(filtrados), 5)
            self._listbox.config(height=altura)
            
            # Insere a lista VISUALMENTE logo abaixo do entry (antes da msg de erro)
            self._listbox.pack(fill="x", after=self._row, pady=(2, 0))
        else:
            self._esconder_lista()

    def _selecionar_item(self, event):
        if not self._listbox.curselection():
            return
        item = self._listbox.get(self._listbox.curselection() or self._listbox.keyselection() )
        self.set(item)
        self._esconder_lista()
        self._disparar()

    def _esconder_lista(self):
        self._listbox.pack_forget()

    def _esconder_lista_delay(self, event):
        self.after(150, self._esconder_lista)

class BotoesFormulario(ctk.CTkFrame):
    """Linha de botões Cancelar/ Salvar- CP-05."""
    
    def __init__(self, master, texto_salvar: str="Salvar",
                 on_salvar= None, on_cancelar=None, **kwargs):
        super().__init__(master,fg_color="transparent", **kwargs)

        ctk.CTkButton(
            self, text="Cancelar", width=110, height=34,
            fg_color=COR_BRANCO, text_color="#3d3d3a",
            border_width=1, border_color=COR_CINZA_B,
            hover_color=COR_CINZA_E,
            command= on_cancelar,
        ).pack(side="left", padx=(0,8))

        ctk.CTkButton(
            self, text= texto_salvar, width= 140, height= 34,
            fg_color= COR_AZUL_M, hover_color="#3d3d3a",
            command= on_salvar,
        ).pack(side="left")


class SecaoFormulario(ctk.CTkFrame):
    """Card com título e linha divisória- agrupa campos relecionados."""

    def __init__(self, master, titulo: str, **kwargs):
        super().__init__(master,fg_color=COR_BRANCO, corner_radius=8,
                         border_width=1, border_color=COR_CINZA_B, **kwargs)
        ctk.CTkLabel(self, text= titulo,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COR_AZUL).pack(anchor="w", padx=14, pady=(12,0))
        ctk.CTkFrame(self, fg_color=COR_CINZA_B, height=1).pack(
            fill="x", padx=14, pady=(6,10))


class FeedbackBanner(ctk.CTkFrame):
    """Banner de feedback- sucesso ou erro- exibido temporariamente"""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", height=0, width=0, **kwargs)
        self._lbl= ctk.CTkLabel(self, text="",font=ctk.CTkFont(size=12),
                                corner_radius=6, padx=12, pady=6 )
        self._timer=None
    
    def sucesso(self, msg: str, duração_ms: int=5000):
        self._lbl.configure(text=msg, fg_color="#EAF3DE", text_color="#27500A")
        self._lbl.pack(fill="x", pady=(8,8))
        self._agendar_ocultar(duração_ms)

    def erro(self, msg: str, duração_ms: int=5000):
        self._lbl.configure(text=msg, fg_color="#FCEBEB", text_color="#A32D2D")
        self._lbl.pack(fill="x", pady=(8,8))
        self._agendar_ocultar(duração_ms)
    
    def aviso(self, msg: str, duração_ms: int=5000):
        self._lbl.configure(text=msg, fg_color="#FAEEDA", text_color="#854F0B")
        self._lbl.pack(fill="x", pady=(8,8))
        self._agendar_ocultar(duração_ms)

    def _agendar_ocultar(self, ms: int):
        if self._timer:
            self.after_cancel(self._timer)
        self._timer=self.after(ms, self._ocultar)
    
    def _limpar(self):
        if self._timer:
            self.after_cancel(self._timer)
            self._timer=None
            self._lbl.pack_forget()

    def _ocultar(self):
        self._lbl.pack_forget()