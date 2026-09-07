"""
MOD-07 · Modulo_07_patrimonio · autorizacao.py
Checagem de permissão compartilhada por PatrimonioService e InventarioService.
"""
from Modulo_01_autenticacao import PermissionGuard
from Modulo_05_admin import UsuarioService

from .excecoes import PermissaoNegadaError


def resolver_usuario_autorizado(usuario_id: int, recurso: str | None = None):
    """
    Checagem em duas camadas, nesta ordem:
      1. Acesso ao SUBSISTEMA (RF-39/RN-21) — TI sempre passa; demais
         perfis exigem acesso_patrimonio=True, concedido só pelo TI.
      2. Se `recurso` for informado, a permissão de PERFIL para essa ação
         específica dentro do subsistema (PermissionGuard).

    Devolve o DadosUsuario resolvido, para o chamador reaproveitar (ex.:
    perfil) sem uma segunda consulta.

    Raises:
        PermissaoNegadaError
    """
    usuario = UsuarioService.buscar(usuario_id)
    if not usuario:
        raise PermissaoNegadaError(f"Usuário {usuario_id} não encontrado.")
    if not usuario.pode_acessar_patrimonio:
        raise PermissaoNegadaError(
            "Você não tem permissão para acessar o módulo de Patrimônio. "
            "Solicite ao TI."
        )
    if recurso and not PermissionGuard.pode_acessar(usuario.perfil.value, recurso):
        raise PermissaoNegadaError(
            f"Perfil '{usuario.perfil.value}' não tem permissão para '{recurso}'."
        )
    return usuario
