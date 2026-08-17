"""MOD-07 · Patrimônio — bens permanentes, etiquetagem e inventário."""
from .patrimonio_service import PatrimonioService
from .dto import (
    ClassificacaoLeitura, SeveridadeLeitura, CodigoAviso, SaidaEtiqueta,
    FiltroBens, DadosBem, DadosManutencao, DadosBaixa, ContextoColeta, AjusteConfirmado,
    ResultadoLeitura, ResumoSessao, Aviso, ResultadoAbertura,
    ResultadoEtiquetas, BemPublico,
)
from .excecoes import (
    PatrimonioError,
    BemNaoEncontradoError, TomboDuplicadoError, BemBaixadoError, MascaraTomboInvalidaError,
    LocalizacaoNaoEncontradaError, LocalizacaoEmUsoError, MovimentacaoInvalidaError,
    BaixaJaRegistradaError, SessaoNaoEncontradaError, SessaoNaoAbertaError,
    EscopoConflitanteError, AjusteNaoConfirmadoError, TokenInvalidoError,
    TokenExpiradoError, TokenRevogadoError, CodigoIlegivelError,
    EtiquetaError, ImpressoraIndisponivelError, PayloadExcedidoError, PermissaoNegadaError,
    AnexoObrigatorioError, AnexoInvalidoError, AnexoExcedidoError,
)

__all__ = [
    "PatrimonioService",
    "ClassificacaoLeitura", "SeveridadeLeitura", "CodigoAviso", "SaidaEtiqueta",
    "FiltroBens", "DadosBem", "DadosManutencao", "DadosBaixa", "ContextoColeta", "AjusteConfirmado",
    "ResultadoLeitura", "ResumoSessao", "Aviso", "ResultadoAbertura",
    "ResultadoEtiquetas", "BemPublico",
    "PatrimonioError",
    "BemNaoEncontradoError", "TomboDuplicadoError", "BemBaixadoError", "MascaraTomboInvalidaError",
    "LocalizacaoNaoEncontradaError", "LocalizacaoEmUsoError", "MovimentacaoInvalidaError",
    "BaixaJaRegistradaError", "SessaoNaoEncontradaError", "SessaoNaoAbertaError",
    "EscopoConflitanteError", "AjusteNaoConfirmadoError", "TokenInvalidoError",
    "TokenExpiradoError", "TokenRevogadoError", "CodigoIlegivelError",
    "EtiquetaError", "ImpressoraIndisponivelError", "PayloadExcedidoError", "PermissaoNegadaError",
    "AnexoObrigatorioError", "AnexoInvalidoError", "AnexoExcedidoError",
]
