"""
gui.componentes.filtro_multiselect.py
FiltroMultiSelect — filtro de seleção múltipla por checkbox (T-11).

Substitui o CTkComboBox de seleção única nos filtros de relatório: um
botão-resumo que abre um painel flutuante com um checkbox por valor.
Lista vazia de selecionados == nenhum filtro aplicado (mesma semântica do
antigo "Todos").
"""
import customtkinter as ctk

from gui.componentes.tema import COR_CINZA_E, COR_CINZA_B, COR_BRANCO


class FiltroMultiSelect(ctk.CTkFrame):
    """Botão + painel flutuante de checkboxes para filtro multi-seleção."""

    def __init__(self, master, label: str, valores: list[str] | None = None,
                 largura: int = 150, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._label = label
        self._valores: list[str] = []
        self._marcados: set[str] = set()
        self._on_change = on_change
        self._painel: ctk.CTkToplevel | None = None

        self._btn = ctk.CTkButton(
            self, text=f"{label} Todos ▾", width=largura, height=32, corner_radius=6,
            fg_color=COR_CINZA_E, text_color="#3d3d3a", hover_color=COR_CINZA_B,
            anchor="w", command=self._alternar_painel,
        )
        self._btn.pack()
        if valores:
            self.configurar_valores(valores)

    def configurar_valores(self, valores: list[str]) -> None:
        """Repopula as opções (chamado após buscar dados), preservando marcações válidas."""
        self._valores = valores
        self._marcados &= set(valores)
        self._atualizar_texto_botao()
        if self._painel is not None:
            self._redesenhar_painel()

    def selecionados(self) -> list[str]:
        """Valores atualmente marcados. Lista vazia == nenhum filtro (equivale a 'Todos')."""
        return sorted(self._marcados)

    def limpar(self) -> None:
        self._marcados.clear()
        self._atualizar_texto_botao()
        if self._painel is not None:
            self._redesenhar_painel()

    def _alternar_painel(self):
        if self._painel is not None:
            self._fechar_painel()
        else:
            self._abrir_painel()

    def _abrir_painel(self):
        self._painel = ctk.CTkToplevel(self)
        self._painel.overrideredirect(True)
        self._painel.attributes("-topmost", True)
        x = self._btn.winfo_rootx()
        y = self._btn.winfo_rooty() + self._btn.winfo_height()
        self._painel.geometry(f"220x260+{x}+{y}")
        self._redesenhar_painel()
        self._painel.bind("<FocusOut>", lambda e: self._fechar_painel())
        self._painel.focus_set()

    def _redesenhar_painel(self):
        for w in self._painel.winfo_children():
            w.destroy()
        scroll = ctk.CTkScrollableFrame(self._painel, fg_color=COR_BRANCO)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        ctk.CTkButton(scroll, text="Limpar seleção", height=24,
                      command=self._marcar_todos_limpo).pack(fill="x", pady=(0, 4))
        for valor in self._valores:
            var = ctk.BooleanVar(value=valor in self._marcados)
            ctk.CTkCheckBox(
                scroll, text=valor, variable=var,
                command=lambda v=valor, var=var: self._alternar_valor(v, var.get()),
            ).pack(anchor="w", pady=2, padx=4)

    def _alternar_valor(self, valor: str, marcado: bool):
        if marcado:
            self._marcados.add(valor)
        else:
            self._marcados.discard(valor)
        self._atualizar_texto_botao()
        if self._on_change:
            self._on_change()

    def _marcar_todos_limpo(self):
        self.limpar()
        if self._on_change:
            self._on_change()

    def _fechar_painel(self):
        if self._painel:
            self._painel.destroy()
            self._painel = None

    def _atualizar_texto_botao(self):
        n = len(self._marcados)
        texto = f"{self._label} Todos ▾" if n == 0 else f"{self._label} {n} selecionado(s) ▾"
        self._btn.configure(text=texto)
