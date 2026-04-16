import bcrypt
class teste:
 def verificar_senha(senha: str, hash_armazenado: str)->bool:
        return bcrypt.checkpw(
            senha.encode("utf-8"),
            hash_armazenado.encode("utf-8")
        )
bcrypt.hashpw(senha.encode("utf-8"),bcrypt.gensalt(rounds=12)).decode("utf-8")