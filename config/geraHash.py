from Modulo_01_autenticacao import AuthService

senha_plana = "teste123"
hash_gerado = AuthService.hash_senha(senha_plana)

print("="*50)
print(f"Senha original: {senha_plana}")
print(f"Hash gerado (copie e cole no banco):")
print(hash_gerado)
print("="*50)