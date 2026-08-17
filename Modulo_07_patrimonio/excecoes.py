"""
MOD-07 · Modulo_07_patrimonio · excecoes.py

Hierarquia de exceções do módulo de patrimônio.

CONTRATO COM A GUI
    Toda exceção daqui herda de PatrimonioError e carrega mensagem já
    redigida para exibição ao usuário — a tela deve capturar
    PatrimonioError e mostrar `str(e)` no FeedbackBanner, sem traduzir
    códigos de erro.

    Exceções que NÃO herdam de PatrimonioError (SQLAlchemyError, OSError,
    socket.error) indicam falha de infraestrutura e devem subir para o
    tratamento genérico da tela, com log.
"""


class PatrimonioError(Exception):
    """Base de todas as exceções de negócio do MOD-07."""


# ─── Bem patrimonial ────────────────────────────────────────────────────────

class BemNaoEncontradoError(PatrimonioError):
    """Tombo ou id inexistente."""


class TomboDuplicadoError(PatrimonioError):
    """
    Violação da RN-09. Não deveria ocorrer pelo fluxo normal, já que o tombo
    é gerado pelo sistema — indica emissão concorrente que escapou do
    bloqueio do TomboGenerator, ou importação manual no banco.
    """


class BemBaixadoError(PatrimonioError):
    """
    Operação inválida sobre bem já baixado (RN-12). Cobre edição,
    transferência, nova baixa e registro de leitura em inventário.
    """


class MascaraTomboInvalidaError(PatrimonioError):
    """
    Máscara configurada não contém o marcador de sequência ou usa formato
    não suportado. Bloqueia o cadastro até o TI corrigir a configuração.
    """


# ─── Localização e movimentação ─────────────────────────────────────────────

class LocalizacaoNaoEncontradaError(PatrimonioError):
    """Id de localização inexistente ou desativada."""


class LocalizacaoEmUsoError(PatrimonioError):
    """
    Tentativa de desativar localização que ainda tem bens ativos lotados
    (RN-10: bem ativo sempre tem uma localização vigente).
    """


class MovimentacaoInvalidaError(PatrimonioError):
    """
    Transferência sem efeito (destino igual à origem) ou com destino
    inválido. Evita gravar linha de histórico que não representa mudança.
    """


class BaixaJaRegistradaError(PatrimonioError):
    """Bem já possui baixa registrada (UNIQUE em baixa_bem.bem_id)."""


# ─── Sessão de inventário ───────────────────────────────────────────────────

class SessaoNaoEncontradaError(PatrimonioError):
    """Id de sessão inexistente."""


class SessaoNaoAbertaError(PatrimonioError):
    """
    Operação que exige sessão aberta foi solicitada sobre sessão finalizada
    ou cancelada.
    """


class EscopoConflitanteError(PatrimonioError):
    """
    Violação da RN-16: já existe sessão aberta com escopo sobreposto.

    A mensagem deve identificar a sessão conflitante, para o usuário saber
    o que fechar antes de abrir a nova.
    """


# NOTA: SnapshotVazioError foi descartado no fechamento do contrato.
# Escopo sem bens ativos não impede a abertura da sessão: vira aviso
# (CodigoAviso.escopo_vazio) no retorno de abrir_sessao, e a tela consulta
# contar_escopo() antes para avisar já na seleção do escopo.


class AjusteNaoConfirmadoError(PatrimonioError):
    """
    Fechamento solicitado com divergências pendentes de decisão (RN-14).
    Nenhuma localização é alterada sem confirmação explícita.
    """


# ─── Pareamento e coleta ────────────────────────────────────────────────────

class TokenInvalidoError(PatrimonioError):
    """Token inexistente ou malformado."""


class TokenExpiradoError(PatrimonioError):
    """Token além de expira_em (RN-19)."""


class TokenRevogadoError(PatrimonioError):
    """Token revogado — manualmente ou pelo fechamento da sessão (RN-19)."""


class CodigoIlegivelError(PatrimonioError):
    """
    Código lido não corresponde a nenhum formato reconhecido: não é URL do
    serviço, não é tombo puro e não bate com a máscara configurada.
    """


# ─── Etiquetas e impressão ──────────────────────────────────────────────────

class EtiquetaError(PatrimonioError):
    """Base das falhas de geração ou emissão de etiqueta."""


class ImpressoraIndisponivelError(EtiquetaError):
    """
    Impressora não respondeu na rede ou fila local inacessível. A mensagem
    deve sugerir a saída em arquivo como alternativa (RF-28.3).
    """


class PayloadExcedidoError(EtiquetaError):
    """
    Payload do QR ultrapassou o limite que mantém a legibilidade no tamanho
    físico definido. Ocorre se host/porta configurados forem longos demais.
    """


# ─── Permissão ──────────────────────────────────────────────────────────────

class PermissaoNegadaError(PatrimonioError):
    """
    Perfil do usuário não autoriza a operação.

    Levantada pelos serviços como segunda linha de defesa: a GUI já deve
    ocultar a ação, mas o serviço não confia na tela. O serviço de coleta
    HTTP depende exclusivamente desta checagem, pois não passa pela GUI.
    """


# ─── Anexo de baixa (v1.8) ──────────────────────────────────────────────────

class AnexoObrigatorioError(PatrimonioError):
    """Baixa sem anexo de PDF (RF-30 revisado, RNF-20)."""


class AnexoInvalidoError(PatrimonioError):
    """
    Arquivo selecionado não é um PDF válido — verificado pela assinatura
    dos bytes (%PDF-), não pela extensão do nome.
    """


class AnexoExcedidoError(PatrimonioError):
    """Anexo acima do limite configurado em baixa_anexo_max_mb."""
