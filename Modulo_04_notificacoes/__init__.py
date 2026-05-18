"""
Modulo_04_notificacoes — interface pública do módulo de notificações.
"""
from .gmail_client          import GmailClient
from .notificacao_service   import NotificacaoService
from .scheduler             import NotificacaoScheduler

__all__ = [
    "GmailClient",
    "NotificacaoService",
    "NotificacaoScheduler",
]