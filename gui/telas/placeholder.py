"""
gui · telas · placeholder.py
Tela placeholder — exibida para módulos ainda não implementados.
Removida progressivamente nas sprints 1 a 6.
"""
import customtkinter as ctk
 
COR_AZUL = "#1F4E79"
COR_CINZA_E = "#F2F1ED"
 
 
class TelaPlaceholder(ctk.CTkFrame):
    """Placeholder visual para telas não implementadas."""
 
    def __init__(self, master, titulo: str):
        super().__init__(master, fg_color=COR_CINZA_E, corner_radius=0)
 
        ctk.CTkFrame(self, fg_color="white", height=44, corner_radius=0,
                     border_width=1, border_color="#E8E6DE").pack(fill="x")
 
        ctk.CTkLabel(
            self,
            text=f"{titulo}",
            text_color=COR_AZUL,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(60, 12))
 
        ctk.CTkLabel(
            self,
            text="Esta tela será implementada na sprint correspondente.",
            text_color="#888780",
            font=ctk.CTkFont(size=13),
        ).pack()
 
        ctk.CTkLabel(
            self,
            text="Sprint 0 — estrutura base concluída",
            text_color="#AAAAAA",
            font=ctk.CTkFont(size=11),
        ).pack(pady=4)