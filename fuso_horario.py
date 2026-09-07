"""
fuso_horario.py — conversão de datetime do banco (UTC) para horário de
Brasília, na exibição ao usuário.

CONTEXTO
    Toda conexão MySQL do projeto força `SET time_zone = '+00:00'`
    (Modulo_06_dados/database.py) e todo timestamp gravado em Python usa
    `datetime.utcnow()` — o banco inteiro guarda UTC "naive" (sem tzinfo),
    de propósito, para não depender do fuso do servidor físico. Esse é o
    lado certo para ficar em UTC; o lado que precisa converter é a
    EXIBIÇÃO, nunca o armazenamento.

    Este módulo não depende de nada do projeto (nem GUI, nem
    Modulo_06_dados) — pode ser importado livremente por qualquer camada
    (telas, serviços, geração de relatório, o processo HTTP do
    ColetaWebService) sem violar a separação entre GUI e acesso a dados.

USO
    Este módulo só CONVERTE (para_horario_brasilia). Cada chamador
    continua responsável pelo próprio `.strftime(...)`, preservando o
    formato que já usava — só passa a chamar sobre o datetime convertido,
    não sobre o valor cru do banco.

        texto = f"{para_horario_brasilia(item.conferido_em):%d/%m/%Y %H:%M}"
        # ou, com fallback para valor ausente:
        texto = formatar(item.conferido_em, "%d/%m/%Y %H:%M")
"""
from datetime import datetime
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
BRASILIA = ZoneInfo("America/Sao_Paulo")


def para_horario_brasilia(dt: datetime | None) -> datetime | None:
    """
    Converte um datetime do banco (UTC, naive na prática) para horário de
    Brasília, aware. None passa direto. Também aceita um datetime já aware
    em outro fuso (não deveria ocorrer neste projeto, mas fica correto).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(BRASILIA)


def formatar(dt: datetime | None, padrao_strftime: str, vazio: str = "—") -> str:
    """Atalho para para_horario_brasilia(dt).strftime(padrao_strftime),
    com fallback textual quando dt é None."""
    convertido = para_horario_brasilia(dt)
    return convertido.strftime(padrao_strftime) if convertido else vazio
