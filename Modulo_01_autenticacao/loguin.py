import customtkinter as ctk
class Login(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Login")
        self.geometry("800x600")
        self.resizable(False, False)

        # Criação dos widgets
        self.label_username = ctk.CTkLabel(self, text="Username:")
        self.entry_username = ctk.CTkEntry(self)
        self.label_password = ctk.CTkLabel(self, text="Password:")
        self.entry_password = ctk.CTkEntry(self, show="*")
        self.button_login = ctk.CTkButton(self, text="Login", command=self.login)

        # Posicionamento dos widgets
        self.label_username.pack(pady=10)
        self.entry_username.pack(pady=10)
        self.label_password.pack(pady=10)
        self.entry_password.pack(pady=10)
        self.button_login.pack(pady=20)

    def login(self):
        username = self.entry_username.get()
        password = self.entry_password.get()
        
        # Aqui você pode adicionar a lógica de autenticação
        if username == "admin" and password == "password":
            print("Login successful!")
            # Você pode abrir a próxima janela ou realizar outras ações aqui
        else:
            print("Invalid credentials!")

main = Login()
main.mainloop()