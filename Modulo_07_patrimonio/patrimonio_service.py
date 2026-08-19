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
    registrar/consultar manutenção                          : tecnico, admin, ti
    baixar_bem                                              : admin, ti
    cadastrar/editar/desativar localização (T-28)           : ti
    configurar máscara de tombo                             : ti

Todo método acima também exige acesso ao subsistema (RF-39/RN-21), checado
por _resolver_usuario_autorizado antes de qualquer checagem de perfil — ver
Bloco 3 do Sprint 10.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from sqlalchemy.exc import IntegrityError

from Modulo_06_dados import get_session, Localizacao, SituacaoBemEnum, MotivoBaixaEnum
from Modulo_05_admin import ConfigService

from .dto import (
    BemPublico, DadosBem, DadosBaixa, DadosManutencao,
    FiltroBens, ResultadoEtiquetas, SaidaEtiqueta,
)
from .excecoes import (
    BemNaoEncontradoError, BemBaixadoError, BaixaJaRegistradaError,
    LocalizacaoNaoEncontradaError, LocalizacaoEmUsoError,
    MovimentacaoInvalidaError, TomboDuplicadoError,
    AnexoObrigatorioError, AnexoInvalidoError, AnexoExcedidoError,
    ImpressoraIndisponivelError, PayloadExcedidoError, CodigoIlegivelError,
)
from .autorizacao import resolver_usuario_autorizado
from .bem_repo import BemRepo
from .localizacao_repo import LocalizacaoRepo
from .manutencao_repo import ManutencaoRepo
from .documento_baixa_repo import DocumentoBaixaRepo
from .tombo_generator import TomboGenerator
from . import etiqueta_builder
from .etiqueta_builder import EtiquetaBuilderError

_ASSINATURA_PDF = b"%PDF-"
_LIMITE_MB_PADRAO = 10
_LIMITE_NOME_ANEXO = 160  # baixa_documento.nome_original é VARCHAR(160)
_CAPACIDADE_QR_V3_M_BYTES = 42  # capacidade de dados (byte mode) do QR versão 3 / ECC M

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

    def listar_bens_com_manutencao(self, usuario_id: int, filtro: FiltroBens | None = None) -> list:
        """
        Mesma listagem de listar_bens, em par com a data da última
        manutenção de cada bem — usada só por T-23 (coluna "Última
        manutenção"). Consulta única (RNF-21/AD-24), sem N+1 por linha.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return BemRepo.listar_com_ultima_manutencao(filtro)

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
        # Caminho público (RE-15/RF-37): NÃO passa por _resolver_usuario_autorizado
        # nem por obter_por_tombo (que agora exige usuario_id) — vai direto ao repo.
        bem = BemRepo.buscar_por_tombo(tombo)
        if not bem:
            raise BemNaoEncontradoError(f"Tombo '{tombo}' não encontrado.")
        ultima_manutencao = ManutencaoRepo.buscar_ultima_por_bem(bem.id)
        return BemPublico(
            tombo=bem.tombo,
            descricao=bem.descricao,
            marca_modelo=bem.marca_modelo,
            localizacao=bem.localizacao.nome_completo,
            situacao=bem.situacao.value,
            baixado=bem.situacao == SituacaoBemEnum.baixado,
            ultima_manutencao=ultima_manutencao.data_manutencao if ultima_manutencao else None,
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

    def baixar_bem(self, bem_id: int, dados: DadosBaixa, usuario_id: int):
        """
        Baixa patrimonial (RF-30 revisado, v1.8). Perfis admin e ti apenas.

        Anexo em PDF obrigatório (RNF-20/AD-22): validado ANTES de abrir
        transação (assinatura de arquivo, não extensão; tamanho contra
        baixa_anexo_max_mb). Em transação única: insere baixa_documento,
        obtém o id, insere baixa_bem referenciando-o, muda situacao para
        'baixado' e grava movimentacao_bem tipo='baixa' — nessa ordem
        exata (DAS v1.5 §5.8). Falha em qualquer ponto desfaz tudo: sem
        documento órfão, sem baixa sem anexo.

        Irreversível pela interface (RN-12). O registro do bem permanece
        para auditoria e sai do escopo de sessões futuras. Reverter exige
        intervenção no banco, deliberadamente.

        Raises:
            BemNaoEncontradoError, BaixaJaRegistradaError, PermissaoNegadaError,
            AnexoObrigatorioError, AnexoInvalidoError, AnexoExcedidoError
        """
        self._resolver_usuario_autorizado(usuario_id, "baixar_bem")

        bem = self.obter_bem(usuario_id, bem_id)
        if bem.situacao == SituacaoBemEnum.baixado:
            raise BaixaJaRegistradaError(f"Bem {bem.tombo} já possui baixa registrada.")

        if not dados.anexo_conteudo:
            raise AnexoObrigatorioError("O anexo em PDF é obrigatório para registrar a baixa.")
        if not dados.anexo_conteudo.startswith(_ASSINATURA_PDF):
            raise AnexoInvalidoError("O arquivo selecionado não é um PDF válido.")
        limite_mb = int(ConfigService.get("baixa_anexo_max_mb") or _LIMITE_MB_PADRAO)
        if len(dados.anexo_conteudo) > limite_mb * 1024 * 1024:
            raise AnexoExcedidoError(f"O anexo excede o limite de {limite_mb} MB.")

        sha256 = hashlib.sha256(dados.anexo_conteudo).hexdigest()
        nome_tratado = self._tratar_nome_anexo(dados.anexo_nome)

        with get_session() as s:
            documento = DocumentoBaixaRepo.criar(
                s, conteudo=dados.anexo_conteudo, nome_original=nome_tratado,
                sha256=sha256, tamanho_bytes=len(dados.anexo_conteudo),
                usuario_id=usuario_id,
            )
            bem = BemRepo.baixar(
                s, bem_id=bem_id, motivo=MotivoBaixaEnum(dados.motivo),
                data_baixa=dados.data_baixa, documento_id=documento.id,
                usuario_id=usuario_id, documento=dados.documento,
                numero_mtr=dados.numero_mtr, numero_laudo=dados.numero_laudo,
                observacao=dados.observacao,
            )

        logger.info("Bem baixado: id=%s usuario_id=%s", bem_id, usuario_id)
        return bem

    def obter_baixa(self, usuario_id: int, bem_id: int):
        """
        Dados da baixa (motivo, data, MTR, laudo) de um bem já baixado,
        para exibição em T-25.

        Raises:
            BemNaoEncontradoError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        baixa = BemRepo.buscar_baixa(bem_id)
        if not baixa:
            raise BemNaoEncontradoError(f"Bem {bem_id} não possui baixa registrada.")
        return baixa

    def obter_documento_baixa(self, usuario_id: int, bem_id: int):
        """
        Anexo (PDF) da baixa de um bem, para download em T-25.

        Raises:
            BemNaoEncontradoError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        documento = DocumentoBaixaRepo.buscar_por_bem_id(bem_id)
        if not documento:
            raise BemNaoEncontradoError(f"Bem {bem_id} não possui documento de baixa.")
        return documento

    # ─── Manutenção (RF-38, v1.8) ────────────────────────────────────────────

    def registrar_manutencao(self, bem_id: int, dados: DadosManutencao, usuario_id: int):
        """
        Registra manutenção realizada em um bem (RF-38). Append-only
        (RN-23) — não altera bem_patrimonial nem gera movimentacao_bem: são
        históricos com propósitos distintos que não se misturam (AD-24).

        Raises:
            BemNaoEncontradoError, BemBaixadoError, PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id, "registrar_manutencao")
        bem = self.obter_bem(usuario_id, bem_id)
        if bem.situacao == SituacaoBemEnum.baixado:
            raise BemBaixadoError(f"Bem {bem.tombo} está baixado e não pode receber manutenção.")

        manutencao = ManutencaoRepo.criar(bem_id, dados, usuario_id)
        logger.info("Manutenção registrada: bem_id=%s usuario_id=%s", bem_id, usuario_id)
        return manutencao

    def historico_manutencao(self, usuario_id: int, bem_id: int) -> list:
        """
        Manutenções do bem em ordem cronológica (T-29). Append-only, igual
        historico_bem: só há o que ler.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return ManutencaoRepo.listar_por_bem(bem_id)

    # ─── Localizações ───────────────────────────────────────────────────────

    def listar_localizacoes(self, usuario_id: int, apenas_ativas: bool = True) -> list:
        """
        Localizações para combos de tela e escopo de sessão.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return LocalizacaoRepo.listar(apenas_ativas)

    def listar_localizacoes_com_contagem(self, usuario_id: int, apenas_ativas: bool = True) -> list:
        """
        Localizações em par com a contagem de bens ativos lotados — só T-28
        (tela exclusiva do TI). Consulta única, sem N+1 por linha.

        Raises:
            PermissaoNegadaError  (somente ti, mesma tela)
        """
        self._resolver_usuario_autorizado(usuario_id, "localizacoes")
        return LocalizacaoRepo.listar_com_contagem_bens(apenas_ativas)

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

    # ─── Etiquetas ────────────────────────────────────────────────────────────

    def listar_impressoras(self, usuario_id: int) -> list[str]:
        """
        Impressoras instaladas na estação, para o seletor usado antes de
        `gerar_etiquetas(saida=impressora_cabo, ...)`. Regra 1: a GUI não
        importa etiqueta_builder diretamente, só este serviço.

        Raises:
            PermissaoNegadaError
        """
        self._resolver_usuario_autorizado(usuario_id)
        return etiqueta_builder.listar_impressoras()

    def gerar_etiquetas(self, bens_ids: list[int], saida: SaidaEtiqueta, usuario_id: int,
                        caminho_destino: str | None = None,
                        nome_impressora: str | None = None) -> ResultadoEtiquetas:
        """
        Gera e emite etiquetas em lote (RF-28), a partir da seleção por
        caixa de seleção em T-23.

        `impressora_rede` não está disponível nesta rodada (decisão de
        escopo) — recusada com ImpressoraIndisponivelError, não implementada
        pela metade. `impressora_cabo` exige `nome_impressora` (lista via
        etiqueta_builder.listar_impressoras()). Saídas em arquivo ignoram
        `caminho_destino` e sempre gravam num diretório temporário,
        devolvido em `ResultadoEtiquetas.caminho_arquivo` — a tela decide
        depois se copia para outro lugar (mesmo padrão de XlsxBuilder/T-11).

        Bem baixado é recusado: etiqueta de bem baixado colada em campo
        gera leitura fantasma na próxima conferência. Em qualquer saída
        bem-sucedida, marca etiqueta_impressa_em nos bens envolvidos.

        Raises:
            BemNaoEncontradoError, BemBaixadoError, PermissaoNegadaError,
            ImpressoraIndisponivelError, PayloadExcedidoError
        """
        self._resolver_usuario_autorizado(usuario_id)

        if not bens_ids:
            raise BemNaoEncontradoError("Nenhum bem selecionado.")

        bens = []
        for bem_id in bens_ids:
            bem = BemRepo.buscar_por_id(bem_id)
            if not bem:
                raise BemNaoEncontradoError(f"Bem {bem_id} não encontrado.")
            if bem.situacao == SituacaoBemEnum.baixado:
                raise BemBaixadoError(
                    f"Bem {bem.tombo} está baixado — etiqueta de bem baixado colada "
                    "em campo gera leitura fantasma na próxima conferência."
                )
            bens.append(bem)

        host = ConfigService.get("coleta_host")
        porta = ConfigService.get("coleta_porta")

        caminho_arquivo = None
        try:
            if saida == SaidaEtiqueta.impressora_rede:
                raise ImpressoraIndisponivelError(
                    "Impressão em rede não está disponível nesta versão — use a impressora local (a cabo)."
                )
            elif saida == SaidaEtiqueta.impressora_cabo:
                if not nome_impressora:
                    raise ImpressoraIndisponivelError("Selecione uma impressora.")
                zpl = etiqueta_builder.gerar_zpl(bens, host, porta)
                etiqueta_builder.imprimir_cabo(zpl, nome_impressora)
            elif saida == SaidaEtiqueta.arquivo_unitario:
                pdf = etiqueta_builder.gerar_pdf_unitario(bens, host, porta)
                caminho_arquivo = self._gravar_arquivo_temp(pdf, "unitario")
            elif saida == SaidaEtiqueta.arquivo_folha:
                pdf = etiqueta_builder.gerar_pdf_folha(bens, host, porta)
                caminho_arquivo = self._gravar_arquivo_temp(pdf, "folha")
            else:
                raise ImpressoraIndisponivelError(f"Saída '{saida}' não suportada.")
        except EtiquetaBuilderError as exc:
            raise PayloadExcedidoError(str(exc)) from exc

        agora = datetime.utcnow()
        BemRepo.marcar_etiqueta_impressa([b.id for b in bens], agora)

        logger.info("Etiquetas geradas: saida=%s quantidade=%s usuario_id=%s",
                    saida.value, len(bens), usuario_id)
        return ResultadoEtiquetas(
            saida=saida, quantidade=len(bens), caminho_arquivo=caminho_arquivo,
            tombos=[b.tombo for b in bens],
        )

    def montar_payload_qr(self, tombo: str) -> str:
        """
        Monta a URL gravada no QR: http://<coleta_host>:<coleta_porta>/p?t=<tombo>

        Host e porta vêm de configuracao (AD-21) e nunca de constante em
        código. O endereço fica gravado dentro de cada etiqueta impressa:
        alterá-lo invalida todas as etiquetas já coladas (R-08).

        Raises:
            PayloadExcedidoError
        """
        host = ConfigService.get("coleta_host")
        porta = ConfigService.get("coleta_porta")
        payload = etiqueta_builder.montar_payload(tombo, host, porta)
        if len(payload.encode("utf-8")) > _CAPACIDADE_QR_V3_M_BYTES:
            raise PayloadExcedidoError(
                f"Payload do QR ('{payload}') excede a capacidade da versão "
                f"{etiqueta_builder.QR_VERSAO}/ECC {etiqueta_builder.QR_ERROR.upper()} "
                f"({_CAPACIDADE_QR_V3_M_BYTES} bytes)."
            )
        return payload

    def resolver_codigo(self, codigo_lido: str) -> str:
        """
        Normaliza qualquer forma de leitura para um tombo.

        Aceita, nesta ordem:
          1. URL completa do serviço  → extrai o parâmetro t
          2. Sequência numérica       → aplica a máscara configurada,
                                        permitindo digitar "1" para PAT-0001
          3. Tombo puro               → vindo do Code 128 ou digitado

        Existe porque as três vias de coleta (leitor 2D, leitor 1D e
        digitação) entregam formatos diferentes para o mesmo bem, e
        InventarioService não deve conhecer essa diferença.

        Raises:
            CodigoIlegivelError
        """
        codigo = (codigo_lido or "").strip()
        if not codigo:
            raise CodigoIlegivelError("Código vazio.")

        if codigo.lower().startswith(("http://", "https://")):
            valores = parse_qs(urlparse(codigo).query).get("t")
            if not valores or not valores[0].strip():
                raise CodigoIlegivelError(f"URL sem o parâmetro 't': '{codigo}'")
            return valores[0].strip()

        if codigo.isdigit():
            mascara = ConfigService.get("patrimonio_mascara_tombo")
            if not mascara:
                raise CodigoIlegivelError("Máscara de tombo não configurada.")
            try:
                return TomboGenerator.aplicar_mascara(mascara, int(codigo))
            except Exception as exc:
                raise CodigoIlegivelError(
                    f"Não foi possível aplicar a máscara ao código '{codigo}': {exc}"
                ) from exc

        return codigo

    # ─── Interno ──────────────────────────────────────────────────────────────

    @staticmethod
    def _gravar_arquivo_temp(conteudo: bytes, prefixo: str) -> str:
        """
        Grava um arquivo de etiquetas gerado num diretório temporário e
        devolve o caminho — mesmo padrão de XlsxBuilder/T-11: o serviço
        nunca abre diálogo de "salvar como", a tela decide depois.
        """
        import tempfile
        from pathlib import Path

        pasta = Path(tempfile.gettempdir()) / "SCU-Uronefrologia" / "etiquetas"
        pasta.mkdir(parents=True, exist_ok=True)
        nome = f"etiquetas_{prefixo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        caminho = pasta / nome
        caminho.write_bytes(conteudo)
        return str(caminho)

    @staticmethod
    def _tratar_nome_anexo(nome: str) -> str:
        """
        Sanitiza o nome do anexo antes de gravar: remove separadores de
        caminho (defesa extra — o nome já deveria vir só do basename) e
        trunca para caber em baixa_documento.nome_original (VARCHAR(160)),
        preservando a extensão. Sem isso, um nome real — gerado por
        scanner ou por um caminho de rede longo, por exemplo — pode
        estourar a coluna e falhar com "Data too long", já que o banco
        roda em STRICT_TRANS_TABLES.
        """
        nome = os.path.basename(nome.replace("\\", "/")).strip()
        if not nome:
            return "documento.pdf"
        if len(nome) <= _LIMITE_NOME_ANEXO:
            return nome
        raiz, ext = os.path.splitext(nome)
        ext = ext[:20]  # extensão absurdamente longa não é extensão de verdade
        return raiz[: _LIMITE_NOME_ANEXO - len(ext)] + ext

    @staticmethod
    def _resolver_usuario_autorizado(usuario_id: int, recurso: str | None = None):
        """
        Checagem de acesso ao subsistema (RF-39/RN-21) + permissão de perfil
        por ação. Compartilhada com InventarioService — ver autorizacao.py.

        Raises:
            PermissaoNegadaError
        """
        return resolver_usuario_autorizado(usuario_id, recurso)
