"""
gui.componentes.tabela_scroll.py

TabelaScroll — área de tabela com scroll vertical E horizontal reais,
usando UMA ÚNICA grade (`self.grade`) compartilhada entre cabeçalho e
linhas de dados.

POR QUE ISSO EXISTE
    CTkScrollableFrame só rola num eixo por vez (não dá pra ter vertical e
    horizontal juntos). E o padrão anterior — cabeçalho num CTkFrame, cada
    linha de dados em OUTRO CTkFrame independente, cada um com seu próprio
    grid_columnconfigure — nunca garante alinhamento: o Tkinter calcula
    largura de coluna por container, então nada força a coluna 5 do
    cabeçalho a ter a mesma largura da coluna 5 da linha 3. Basta um texto
    um pouco mais longo numa linha pra desalinhar só aquela linha.

    Aqui, cabeçalho (row=0) e cada linha de dados (row=1, 2, 3...) são
    filhos do MESMO frame (`self.grade`), com uma ÚNICA
    grid_columnconfigure — o Tkinter resolve a largura de cada coluna
    considerando a tabela inteira de uma vez, então alinhamento é garantido
    por construção, não por coincidência de larguras declaradas batendo.

USO
    tabela = TabelaScroll(self)
    tabela.pack(fill="both", expand=True)
    tabela.grade.grid_columnconfigure(...)   # uma vez, cobre cabeçalho e linhas
    ctk.CTkLabel(tabela.grade, ...).grid(row=0, column=0, ...)   # cabeçalho
    ctk.CTkLabel(tabela.grade, ...).grid(row=1, column=0, ...)   # linha 1
    ...
    tabela.limpar_linhas(a_partir_da_row=1)   # remove só as linhas, mantém cabeçalho
"""
import tkinter as tk

import customtkinter as ctk


class TabelaScroll(ctk.CTkFrame):
    """Scroll vertical + horizontal sobre uma grade única (cabeçalho + linhas)."""

    def __init__(self, master, fg_color_grade: str = "#FFFFFF", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Canvas puro (não CTk): precisa de xview/yview programável para
        # as duas scrollbars, que CTkScrollableFrame não expõe.
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=fg_color_grade)
        self._vsb = ctk.CTkScrollbar(self, orientation="vertical", command=self._canvas.yview)
        self._hsb = ctk.CTkScrollbar(self, orientation="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._vsb.set, xscrollcommand=self._hsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # cabeçalho E linhas de dados são filhos deste ÚNICO frame.
        self.grade = ctk.CTkFrame(self._canvas, fg_color=fg_color_grade, corner_radius=0)
        self._janela_id = self._canvas.create_window((0, 0), window=self.grade, anchor="nw")

        self.grade.bind("<Configure>", self._sincronizar_scrollregion)
        self._canvas.bind("<Configure>", self._ajustar_largura_minima)

        self._canvas.bind("<Enter>", self._ativar_scroll_mouse)
        self._canvas.bind("<Leave>", self._desativar_scroll_mouse)

    # ── Geometria ────────────────────────────────────────────────────────────

    def _sincronizar_scrollregion(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _ajustar_largura_minima(self, event):
        # Se a grade for mais estreita que a área visível, estica pra
        # preencher — evita uma faixa vazia à direita quando a tabela cabe
        # sem precisar de scroll horizontal.
        largura_grade = self.grade.winfo_reqwidth()
        largura_alvo = max(event.width, largura_grade)
        self._canvas.itemconfigure(self._janela_id, width=largura_alvo)

    # ── Scroll por mouse (ativo só com o cursor sobre a tabela) ─────────────

    def _ativar_scroll_mouse(self, event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel_vertical)
        self._canvas.bind_all("<Shift-MouseWheel>", self._on_mousewheel_horizontal)

    def _desativar_scroll_mouse(self, event=None):
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Shift-MouseWheel>")

    def _on_mousewheel_vertical(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_horizontal(self, event):
        self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Utilidade ────────────────────────────────────────────────────────────

    def limpar_linhas(self, a_partir_da_row: int = 1):
        """Remove só as linhas de dados (grid row >= a_partir_da_row), mantém o cabeçalho."""
        for w in self.grade.winfo_children():
            info = w.grid_info()
            if info and int(info.get("row", 0)) >= a_partir_da_row:
                w.destroy()

    def voltar_ao_topo(self):
        self._canvas.yview_moveto(0)
        self._canvas.xview_moveto(0)

    def destroy(self):
        self._desativar_scroll_mouse()
        super().destroy()
