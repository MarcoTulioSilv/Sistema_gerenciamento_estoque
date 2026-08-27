"""
Modulo_01_autenticacao . permission_guard.py
Sprint 1 - PermissionGuard: define quais perfis acessam quias telas e ações.
Fonte de verdade única de permissões- consultado pela GUI e pelos serviços.
"""
import logging

logger= logging.getLogger(__name__)

#Mapa de permissões: tela/ação-> perfis permitidos
#Baseado na matriz de rastreabilidade da ERS v1.5 e no inventário de telas

_PERMISSOES: dict[str,list[str]]={
    # Telas — todos os perfis
    "t01_login":       ["tecnico", "admin", "ti"],
    "t02_inicio":      ["tecnico", "admin", "ti"],
    "t21_troca_senha": ["tecnico", "admin", "ti"],
    # Telas — Técnico e TI
    "t03_produtos":       ["tecnico", "ti"],
    "t04_fornecedores":   ["tecnico", "ti", "admin"],
    "t05_novo_produto":   ["ti", "admin"],
    "t06_novo_fornecedor":["ti", "admin"],
    "t07_entrada_manual": ["tecnico","admin"],
    "t08_importar_nfe":   ["tecnico","admin"],
    "t09_retirada":       ["tecnico"],
    # Telas — todos
    "t10_posicao_estoque":["tecnico", "admin", "ti"],
    "t22_dashboard":      ["tecnico", "admin","ti"],
    # Telas — admin e TI
    "t11_relatorios":     ["admin", "ti"],
    "t13_estoque_minimo": ["admin", "ti"],
    "t14_consulta_admin":["admin", "ti"],
    # Telas — apenas TI
    "t12_agendamento":    ["ti"],
    "t15_usuarios":       ["ti"],
    "t16_novo_usuario":   ["ti"],
    "t17_gmail":          ["ti"],
    "t18_backup":         ["ti"],
    "t19_log":            ["ti"],
    "t20_agendamento_ti": ["ti"],
    # Ações de negócio (usadas pelos serviços)
    "registrar_entrada":  ["tecnico","admin", "ti"],
    "registrar_retirada": ["tecnico","admin", "ti"],
    "registrar_transferencia": ["tecnico","admin", "ti"],
    "gerar_relatorio":    ["admin", "ti"],
    "alterar_estoque_minimo": ["admin", "ti"],
    "gerenciar_usuarios": ["ti"],
    "acessar_backup":     ["ti"],
    "ver_log":            ["ti"],
    # MOD-07 — Patrimônio (Sprint 9)
    "bens_patrimoniais":     ["tecnico", "admin", "ti"],
    "novo_bem":               ["tecnico", "admin", "ti"],
    "movimentar_bem":         ["tecnico", "admin", "ti"],
    "baixar_bem":             ["admin", "ti"],
    "cadastrar_localizacao":  ["ti"],
    "editar_localizacao":     ["ti"],
    "desativar_localizacao":  ["ti"],
    # MOD-07 — Patrimônio v1.8 (Sprint 10, Bloco 4)
    "localizacoes":          ["ti"],                     # T-28 — RF-27
    "registrar_manutencao":  ["tecnico", "admin", "ti"],  # RF-38
    # MOD-07 — Patrimônio (Sprint 11 — InventarioService / T-26)
    "abrir_sessao_inventario":   ["admin", "ti"],
    "fechar_sessao_inventario":  ["admin", "ti"],
    "cancelar_sessao_inventario":["admin", "ti"],
    # MOD-07 — Patrimônio (T-27 — relatórios)
    "relatorios_patrimonio": ["admin", "ti"],  # RF-35 — Gestora (admin) + TI
}

class PermissionGuard:
    """
    Verifica se um perfil tem permissão
    """
    @staticmethod
    def pode_acessar(perfil: str,recurso:str)->bool:
        """
        Retorna True se o perfil tem permissão
        Args:
            perfil: valor ENUM de um perfil
            recurso: identificador de tela ou ação
        """

        permitidos= _PERMISSOES.get(recurso,[])
        resultado= perfil in permitidos

        if not resultado:
            logger.debug("Acesso negado: perfil='%s' tentou acessar '%s'", perfil, recurso)
        return resultado
    
    @staticmethod
    def perfis_permitidos(recurso:str)-> list[str]:
        """Retorna a lista de perfis que podem acessar o recurso"""
        return _PERMISSOES.get(recurso,[])
    
    @staticmethod
    def exigir_permissao(perfil:str, recurso: str)->None:
        """
        Lança PermissonError se o perfil não tem acesso.
        Usado pelos serviços para proteção em nivel de negócio.
        """
        if not PermissionGuard.pode_acessar(perfil, recurso):
            raise PermissionError(
                f"Perfil '{perfil}' não tem permissão para '{recurso}'"
            )