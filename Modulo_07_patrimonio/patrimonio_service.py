"""
MOD-07 · Modulo_07_patrimonio · patrimonio_service.py

CONTRATO PÚBLICO — bens, localizações, movimentação, baixa e etiquetas.

REGRAS ARQUITETURAIS QUE VALEM PARA TODO MÉTODO AQUI
    - A GUI importa apenas este serviço. Nunca repos, nunca MOD-06.
    - Todo método que escreve recebe usuario_id e grava rastreabilidade.
    - Escrita usa get_session(); leitura usa get_read_session(). Usar a
      sessão errada em escrita causa rollback silencioso — o dado aparece
      no log e nunca é gravado.
    - Toda operação composta (bem + movimentação, baixa + movimentação)
      ocorre em transação única.
    - Permissão é verificada aqui, não só na tela (ver PermissaoNegadaError).

MATRIZ DE PERMISSÃO (perfis reais do banco: tecnico, admin, ti)
    consultar / cadastrar / editar / etiquetar / transferir : tecnico, admin, ti
    baixar_bem                                              : admin, ti
    cadastrar/editar/desativar localização                  : ti
    configurar máscara de tombo                             : ti
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.exc import IntegrityError

from Modulo_06_dados import get_session, Localizacao, SituacaoBemEnum, MotivoBaixaEnum
from Modulo_01_autenticacao import PermissionGuard
from Modulo_05_admin import UsuarioService

from .dto import (
    BemPublico, DadosBem, FiltroBens, ResultadoEtiquetas, SaidaEtiqueta,
)
from .excecoes import (
    BemNaoEncontradoError, BemBaixadoError, BaixaJaRegistradaError,
    LocalizacaoNaoEncontradaError, LocalizacaoEmUsoError,
    MovimentacaoInvalidaError, TomboDuplicadoError, PermissaoNegadaError,
)
from .bem_repo import BemRepo
from .localizacao_repo import LocalizacaoRepo
from .tombo_generator import TomboGenerator

logger = logging.getLogger(__name__)


class PatrimonioService:
    """Fachada de MOD-07 para bens patrimoniais e etiquetagem."""

    # ─── Consulta ───────────────────────────────────────────────────────────
    #
    # RNF-19 (v1.8): a verificação de acesso ao subsistema ocorre no serviço,
    # não só na tela. Por isso os métodos de consulta abaixo passaram a
    # exigir usuario_id, mesmo os que não têm restrição de perfil — a GUI já
    # oculta o caminho, mas o serviço não confia nela.

    def listar_bens(self, usuario_id: int, filtro: FiltroBens | None = None) -> list:
        """
        Lista bens conforme filtro. Devolve entidades BemPatrimonial já
        desanexadas da sessão (expunge_all no repo).

        Usada por T-23. Sem filtro, devolve apenas bens ativos — a listagem
        padrão não deve mostrar baixados, que só aparecem sob filtro
        explícito.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return BemRepo.listar(filtro)

    def obter_bem(self, usuario_id: int, bem_id: int):
        """
        Raises:
            BemNaoEncontradoError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        bem = BemRepo.buscar_por_id(bem_id)
        if not bem:
            raise BemNaoEncontradoError(f"Bem {bem_id} não encontrado.")
        return bem

    def obter_por_tombo(self, usuario_id: int, tombo: str):
        """
        Busca pelo tombo, aceitando o valor com ou sem espaços em volta e
        insensível a caixa.

        Raises:
            BemNaoEncontradoError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        bem = BemRepo.buscar_por_tombo(tombo)
        if not bem:
            raise BemNaoEncontradoError(f"Tombo '{tombo}' não encontrado.")
        return bem

    def historico_bem(self, usuario_id: int, bem_id: int) -> list:
        """
        Movimentações do bem em ordem cronológica, incluindo o cadastro
        inicial e a baixa. Histórico é append-only (RN-11): nunca há o que
        editar aqui, só o que ler.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return BemRepo.historico(bem_id)

    def consultar_publico(self, tombo: str) -> BemPublico:
        """
        Projeção para a página móvel de consulta (RF-37).

        Sem autenticação: acessível a qualquer dispositivo da rede interna
        que leia o QR. Por isso devolve BemPublico, que omite valor de
        aquisição, nota fiscal e id interno.

        Raises:
            BemNaoEncontradoError
        """
        bem = self.obter_por_tombo(tombo)
        return BemPublico(
            tombo=bem.tombo,
            descricao=bem.descricao,
            marca_modelo=bem.marca_modelo,
            localizacao=bem.localizacao.nome_completo,
            situacao=bem.situacao.value,
            baixado=bem.situacao == SituacaoBemEnum.baixado,
        )

    # ─── Cadastro e edição ──────────────────────────────────────────────────

    def cadastrar_bem(self, dados: DadosBem, usuario_id: int):
        """
        Cadastra um bem e emite seu tombo (RF-25, RF-26).

        Em transação única:
          1. Emite o tombo via TomboGenerator, com SELECT ... FOR UPDATE na
             linha de configuracao que guarda a sequência — é o que impede
             colisão entre duas estações cadastrando ao mesmo tempo.
          2. Insere o bem com situacao='ativo'.
          3. Grava movimentacao_bem tipo='cadastro' com
             localizacao_destino_id preenchida e origem nula.

        Falha em qualquer passo desfaz os três: não existe bem sem tombo,
        nem bem sem linha de histórico.

        Raises:
            LocalizacaoNaoEncontradaError
            MascaraTomboInvalidaError
            TomboDuplicadoError
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        try:
            with get_session() as s:
                loc = s.get(Localizacao, dados.localizacao_id)
                if not loc:
                    raise LocalizacaoNaoEncontradaError(
                        f"Localização {dados.localizacao_id} não encontrada."
                    )
                tombo = TomboGenerator.emitir(s)
                bem = BemRepo.criar(s, tombo=tombo, dados=dados, usuario_id=usuario_id)
        except IntegrityError as exc:
            raise TomboDuplicadoError(
                "Falha ao emitir tombo: número já em uso. Tente novamente."
            ) from exc

        logger.info("Bem cadastrado: tombo=%s usuario_id=%s", bem.tombo, usuario_id)
        return bem

    def editar_bem(self, bem_id: int, dados: DadosBem, usuario_id: int):
        """
        Edita campos descritivos. NÃO altera tombo (RN-09) nem localização —
        mudança de lotação é transferência, e gera histórico (RF-29).

        Se dados.localizacao_id diferir da atual, o método levanta
        MovimentacaoInvalidaError em vez de mover em silêncio: caso
        contrário a alteração escaparia do histórico.

        Raises:
            BemNaoEncontradoError, BemBaixadoError, MovimentacaoInvalidaError,
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        bem = self.obter_bem(usuario_id, bem_id)
        if bem.situacao == SituacaoBemEnum.baixado:
            raise BemBaixadoError(f"Bem {bem.tombo} está baixado e não pode ser editado.")
        if dados.localizacao_id != bem.localizacao_id:
            raise MovimentacaoInvalidaError(
                "Edição não altera localização — use transferir_bem."
            )

        bem = BemRepo.atualizar(bem_id, dados)
        logger.info("Bem editado: id=%s usuario_id=%s", bem_id, usuario_id)
        return bem

    # ─── Movimentação e baixa ───────────────────────────────────────────────

    def transferir_bem(self, bem_id: int, localizacao_destino_id: int,
                       motivo: str, usuario_id: int):
        """
        Move o bem de localização (RF-29), em transação única: atualiza
        bem_patrimonial.localizacao_id e grava movimentacao_bem
        tipo='transferencia' com origem e destino.

        Destino igual à origem levanta MovimentacaoInvalidaError — gravar
        histórico de uma mudança que não houve polui a auditoria.

        Raises:
            BemNaoEncontradoError, BemBaixadoError,
            LocalizacaoNaoEncontradaError, MovimentacaoInvalidaError,
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        bem = self.obter_bem(usuario_id, bem_id)
        if bem.situacao == SituacaoBemEnum.baixado:
            raise BemBaixadoError(f"Bem {bem.tombo} está baixado e não pode ser transferido.")
        if localizacao_destino_id == bem.localizacao_id:
            raise MovimentacaoInvalidaError("Destino é igual à localização atual.")
        if not LocalizacaoRepo.buscar_por_id(localizacao_destino_id):
            raise LocalizacaoNaoEncontradaError(
                f"Localização {localizacao_destino_id} não encontrada."
            )

        bem = BemRepo.transferir(bem_id, localizacao_destino_id, motivo, usuario_id)
        logger.info("Bem transferido: id=%s destino=%s usuario_id=%s",
                     bem_id, localizacao_destino_id, usuario_id)
        return bem

    def baixar_bem(self, bem_id: int, motivo: str, data_baixa: date,
                   usuario_id: int, documento: str | None = None,
                   observacao: str | None = None):
        """
        Baixa patrimonial (RF-30). Perfis admin e ti apenas.

        Em transação única: insere baixa_bem, muda situacao para 'baixado' e
        grava movimentacao_bem tipo='baixa'.

        Irreversível pela interface (RN-12). O registro do bem permanece
        para auditoria e sai do escopo de sessões futuras. Reverter exige
        intervenção no banco, deliberadamente.

        Raises:
            BemNaoEncontradoError, BaixaJaRegistradaError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id, "baixar_bem")

        bem = self.obter_bem(usuario_id, bem_id)
        if bem.situacao == SituacaoBemEnum.baixado:
            raise BaixaJaRegistradaError(f"Bem {bem.tombo} já possui baixa registrada.")

        bem = BemRepo.baixar(
            bem_id, motivo=MotivoBaixaEnum(motivo), data_baixa=data_baixa,
            usuario_id=usuario_id, documento=documento, observacao=observacao,
        )
        logger.info("Bem baixado: id=%s usuario_id=%s", bem_id, usuario_id)
        return bem

    # ─── Localizações ───────────────────────────────────────────────────────

    def listar_localizacoes(self, usuario_id: int, apenas_ativas: bool = True) -> list:
        """
        Localizações para combos de tela e escopo de sessão.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return LocalizacaoRepo.listar(apenas_ativas)

    def cadastrar_localizacao(self, setor: str, sala: str, usuario_id: int,
                              descricao: str | None = None):
        """
        Raises:
            PermissaoNegadaError  (somente ti)
        """
        self._resolver_usuario_autorizado(usuario_id, "cadastrar_localizacao")
        loc = LocalizacaoRepo.criar(setor, sala, descricao)
        logger.info("Localização cadastrada: id=%s usuario_id=%s", loc.id, usuario_id)
        return loc

    def editar_localizacao(self, localizacao_id: int, setor: str, sala: str,
                           usuario_id: int, descricao: str | None = None):
        """
        Raises:
            LocalizacaoNaoEncontradaError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id, "editar_localizacao")
        if not LocalizacaoRepo.buscar_por_id(localizacao_id):
            raise LocalizacaoNaoEncontradaError(f"Localização {localizacao_id} não encontrada.")

        loc = LocalizacaoRepo.editar(localizacao_id, setor, sala, descricao)
        logger.info("Localização editada: id=%s usuario_id=%s", localizacao_id, usuario_id)
        return loc

    def desativar_localizacao(self, localizacao_id: int, usuario_id: int):
        """
        Desativação lógica. Recusada se houver bem ativo lotado ali: RN-10
        exige que todo bem ativo tenha uma localização vigente, e desativar
        deixaria bens órfãos.

        Não há exclusão física — o histórico referencia localizações antigas.

        Raises:
            LocalizacaoNaoEncontradaError, LocalizacaoEmUsoError,
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id, "desativar_localizacao")

        loc = LocalizacaoRepo.buscar_por_id(localizacao_id)
        if not loc:
            raise LocalizacaoNaoEncontradaError(f"Localização {localizacao_id} não encontrada.")
        if LocalizacaoRepo.contar_bens_ativos(localizacao_id) > 0:
            raise LocalizacaoEmUsoError(
                f"Localização '{loc.nome_completo}' tem bens ativos lotados "
                "e não pode ser desativada."
            )

        LocalizacaoRepo.desativar(localizacao_id)
        logger.info("Localização desativada: id=%s usuario_id=%s", localizacao_id, usuario_id)

    # ─── Tombo ──────────────────────────────────────────────────────────────

    def previsualizar_tombo(self, usuario_id: int) -> str:
        """
        Número do próximo tombo, para exibição em T-24 (não faz parte do
        contrato original — adicionado a pedido do usuário para T-24 mostrar
        o número real em vez de um texto genérico).

        NÃO reserva o número: é uma leitura sem lock (ver
        TomboGenerator.previsualizar). Se outra estação cadastrar um bem
        entre a exibição e o salvamento, o tombo final pode diferir deste.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return TomboGenerator.previsualizar()

    # ─── Etiquetas (Sprint 10) ───────────────────────────────────────────────

    def gerar_etiquetas(self, bens_ids: list[int], saida: SaidaEtiqueta,
                        caminho_destino: str | None = None) -> ResultadoEtiquetas:
        """
        Gera e emite etiquetas em lote (RF-28), a partir da seleção por
        caixa de seleção em T-23.

        As quatro saídas consomem a MESMA definição de layout em milímetros
        (AD-17) — é o que garante que a etiqueta térmica e o arquivo
        enviado à gráfica saiam dimensionalmente idênticos:

            impressora_rede   socket TCP na porta configurada
            impressora_cabo   spooler do Windows em modo RAW
            arquivo_unitario  vetorial 100×50 mm, uma etiqueta por página
            arquivo_folha     A4 em grade, com marcas de corte

        Bem baixado é recusado: etiqueta de bem baixado colada em campo
        gera leitura fantasma na próxima conferência.

        Raises:
            BemNaoEncontradoError, BemBaixadoError,
            ImpressoraIndisponivelError, PayloadExcedidoError
        """
        raise NotImplementedError

    def montar_payload_qr(self, tombo: str) -> str:
        """
        Monta a URL gravada no QR: http://<coleta_host>:<coleta_porta>/p?t=<tombo>

        Host e porta vêm de configuracao (AD-21) e nunca de constante em
        código. O endereço fica gravado dentro de cada etiqueta impressa:
        alterá-lo invalida todas as etiquetas já coladas (R-08).

        Raises:
            PayloadExcedidoError
        """
        raise NotImplementedError

    def resolver_codigo(self, codigo_lido: str) -> str:
        """
        Normaliza qualquer forma de leitura para um tombo.

        Aceita, nesta ordem:
          1. URL completa do serviço  → extrai o parâmetro t
          2. Tombo puro               → vindo do Code 128 ou digitado
          3. Sequência numérica       → aplica a máscara configurada,
                                        permitindo digitar "1" para PAT-0001

        Existe porque as três vias de coleta (leitor 2D, leitor 1D e
        digitação) entregam formatos diferentes para o mesmo bem, e
        InventarioService não deve conhecer essa diferença.

        Raises:
            CodigoIlegivelError
        """
        raise NotImplementedError

    # ─── Interno ──────────────────────────────────────────────────────────────

    @staticmethod
    def _resolver_usuario_autorizado(usuario_id: int, recurso: str | None = None):
        """
        Checagem em duas camadas, nesta ordem:
          1. Acesso ao SUBSISTEMA (RF-39/RN-21) — TI sempre passa; demais
             perfis exigem acesso_patrimonio=True, concedido só pelo TI.
          2. Se `recurso` for informado, a permissão de PERFIL para essa
             ação específica dentro do subsistema (PermissionGuard),
             igual ao que já valia antes do controle de acesso da v1.8.

        Devolve o DadosUsuario resolvido, para o chamador reaproveitar
        (ex.: perfil) sem uma segunda consulta.

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
