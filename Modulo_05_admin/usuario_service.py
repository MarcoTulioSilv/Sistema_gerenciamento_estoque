"""
Modulo_05_admin · usuario_service.py
Sprint 6 — UsuarioService: criar, editar, desativar, redefinir senha.

Responsabilidades:
  - Validações de negócio (login único, proteção do último TI ativo).
  - Hash bcrypt das senhas — nunca armazenadas em texto plano.
  - Interface limpa para as telas T-15 e T-16 (sem lógica de banco na GUI).

Regras:
  - RNF-05: senhas armazenadas como bcrypt hash.
  - UC-09 : TI não pode desativar o único usuário TI ativo.
"""
import logging
from dataclasses import dataclass

import bcrypt

from Modulo_06_dados import get_session, get_read_session, Usuario, PerfilEnum

logger = logging.getLogger(__name__)


# ── DTO de saída — desacoplado do modelo ORM ──────────────────────────────────

@dataclass
class DadosUsuario:
    id:                 int
    nome:               str
    login:              str
    perfil:             PerfilEnum
    ativo:              bool
    criado_em:          str   # já formatado para exibição
    acesso_patrimonio:  bool = False  # RF-39 — permissão explícita, ortogonal ao perfil

    @property
    def pode_acessar_patrimonio(self) -> bool:
        """RN-21 — TI acessa por definição; demais dependem de acesso_patrimonio."""
        return self.perfil == PerfilEnum.ti or self.acesso_patrimonio


# ─────────────────────────────────────────────────────────────────────────────

class UsuarioService:
    """Casos de uso de administração de usuários (UC-09, RF-18)."""

    # ── Consultas ─────────────────────────────────────────────────────────────

    @staticmethod
    def listar() -> list[DadosUsuario]:
        """Retorna todos os usuários ordenados por nome."""
        with get_read_session() as s:
            usuarios = s.query(Usuario).order_by(Usuario.nome).all()
            return [
                DadosUsuario(
                    id                = u.id,
                    nome              = u.nome,
                    login             = u.login,
                    perfil            = u.perfil,
                    ativo             = u.ativo,
                    criado_em         = u.criado_em.strftime("%d/%m/%Y") if u.criado_em else "—",
                    acesso_patrimonio = u.acesso_patrimonio,
                )
                for u in usuarios
            ]

    @staticmethod
    def buscar(usuario_id: int) -> DadosUsuario | None:
        """Retorna dados de um usuário pelo ID."""
        with get_read_session() as s:
            u = s.get(Usuario, usuario_id)
            if not u:
                return None
            return DadosUsuario(
                id                = u.id,
                nome              = u.nome,
                login             = u.login,
                perfil            = u.perfil,
                ativo             = u.ativo,
                criado_em         = u.criado_em.strftime("%d/%m/%Y") if u.criado_em else "—",
                acesso_patrimonio = u.acesso_patrimonio,
            )

    # ── Criação ───────────────────────────────────────────────────────────────

    @staticmethod
    def criar(
        nome:   str,
        login:  str,
        senha:  str,
        perfil: PerfilEnum,
        acesso_patrimonio: bool = False,
    ) -> DadosUsuario:
        """
        Cria um novo usuário.

        Raises:
            ValueError: nome/login/senha ausentes, senha fraca, login duplicado.
        """
        UsuarioService._validar_campos(nome, login, senha, novo=True)

        with get_session() as s:
            if s.query(Usuario).filter_by(login=login).first():
                raise ValueError(f"Login '{login}' já está em uso.")

            senha_hash = _hash_senha(senha)
            u = Usuario(
                nome       = nome.strip(),
                login      = login.strip(),
                senha_hash = senha_hash,
                perfil     = perfil,
                ativo      = True,
                acesso_patrimonio = acesso_patrimonio,
            )
            s.add(u)
            s.flush()
            resultado = DadosUsuario(
                id=u.id, nome=u.nome, login=u.login,
                perfil=u.perfil, ativo=u.ativo, criado_em="—",
                acesso_patrimonio=u.acesso_patrimonio,
            )

        logger.info("Usuário criado: login=%s perfil=%s", login, perfil)
        return resultado

    # ── Edição ────────────────────────────────────────────────────────────────

    @staticmethod
    def editar(
        usuario_id: int,
        nome:       str,
        login:      str,
        perfil:     PerfilEnum,
        nova_senha: str | None = None,
        acesso_patrimonio: bool = False,
    ) -> DadosUsuario:
        """
        Edita dados de um usuário existente.
        Se nova_senha for None ou vazia, a senha não é alterada.

        Raises:
            ValueError: usuário inexistente, campos inválidos, login duplicado.
        """
        UsuarioService._validar_campos(nome, login, nova_senha or "placeholder", novo=False)

        if nova_senha and len(nova_senha) < 8:
            raise ValueError("Nova senha deve ter no mínimo 8 caracteres.")

        with get_session() as s:
            u = s.get(Usuario, usuario_id)
            if not u:
                raise ValueError("Usuário não encontrado.")

            # Login duplicado em outro usuário
            duplicado = (s.query(Usuario)
                         .filter(Usuario.login == login.strip(),
                                 Usuario.id    != usuario_id)
                         .first())
            if duplicado:
                raise ValueError(f"Login '{login}' já está em uso por outro usuário.")

            u.nome   = nome.strip()
            u.login  = login.strip()
            u.perfil = perfil
            u.acesso_patrimonio = acesso_patrimonio

            if nova_senha:
                u.senha_hash = _hash_senha(nova_senha)

            resultado = DadosUsuario(
                id=u.id, nome=u.nome, login=u.login,
                perfil=u.perfil, ativo=u.ativo,
                criado_em=u.criado_em.strftime("%d/%m/%Y") if u.criado_em else "—",
                acesso_patrimonio=u.acesso_patrimonio,
            )

        logger.info("Usuário editado: id=%s login=%s", usuario_id, login)
        return resultado

    # ── Desativar / Reativar ──────────────────────────────────────────────────

    @staticmethod
    def desativar(usuario_id: int) -> None:
        """
        Desativa um usuário (ativo = False).

        Raises:
            ValueError: usuário não encontrado ou é o único TI ativo (UC-09).
        """
        with get_session() as s:
            u = s.get(Usuario, usuario_id)
            if not u:
                raise ValueError("Usuário não encontrado.")
            if not u.ativo:
                raise ValueError("Usuário já está inativo.")

            # UC-09: proteger o último TI ativo
            if u.perfil == PerfilEnum.ti:
                ti_ativos = (s.query(Usuario)
                             .filter_by(perfil=PerfilEnum.ti, ativo=True)
                             .count())
                if ti_ativos <= 1:
                    raise ValueError(
                        "Não é possível desativar o único usuário TI ativo. "
                        "Crie ou reative outro usuário TI antes."
                    )

            u.ativo = False

        logger.info("Usuário desativado: id=%s", usuario_id)

    @staticmethod
    def reativar(usuario_id: int) -> None:
        """Reativa um usuário desativado."""
        with get_session() as s:
            u = s.get(Usuario, usuario_id)
            if not u:
                raise ValueError("Usuário não encontrado.")
            if u.ativo:
                raise ValueError("Usuário já está ativo.")
            u.ativo = True

        logger.info("Usuário reativado: id=%s", usuario_id)

    # ── Redefinir senha (pelo TI) ─────────────────────────────────────────────

    @staticmethod
    def redefinir_senha(usuario_id: int, nova_senha: str) -> None:
        """
        Redefine a senha de um usuário sem exigir a senha atual.
        Usado pelo TI em T-16.

        Raises:
            ValueError: senha fraca ou usuário inexistente.
        """
        if not nova_senha or len(nova_senha) < 8:
            raise ValueError("A nova senha deve ter no mínimo 8 caracteres.")

        with get_session() as s:
            u = s.get(Usuario, usuario_id)
            if not u:
                raise ValueError("Usuário não encontrado.")
            u.senha_hash = _hash_senha(nova_senha)

        logger.info("Senha redefinida pelo TI: usuario_id=%s", usuario_id)

    # ── Validação interna ─────────────────────────────────────────────────────

    @staticmethod
    def _validar_campos(nome: str, login: str, senha: str, novo: bool) -> None:
        if not nome or not nome.strip():
            raise ValueError("Nome é obrigatório.")
        if not login or not login.strip():
            raise ValueError("Login é obrigatório.")
        if novo:
            if not senha:
                raise ValueError("Senha é obrigatória para novos usuários.")
            if len(senha) < 8:
                raise ValueError("Senha deve ter no mínimo 8 caracteres.")


# ── Utilitários internos ──────────────────────────────────────────────────────

def _hash_senha(senha: str) -> str:
    """Gera bcrypt hash com salt. Nunca armazenar senha em texto plano (RNF-05)."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
