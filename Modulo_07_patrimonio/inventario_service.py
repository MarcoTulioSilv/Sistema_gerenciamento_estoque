"""
MOD-07 · Modulo_07_patrimonio · inventario_service.py

CONTRATO PÚBLICO — sessões de inventário, pareamento e coleta.

Este é o núcleo do módulo. registrar_leitura é o único ponto que aplica a
árvore de decisão da ERS §3.2, e é chamado pelas três vias de coleta —
leitor na estação, digitação e dispositivo móvel pareado. Nenhuma regra de
classificação existe fora dele; em particular, o serviço HTTP não decide
nada, apenas resolve o token e delega.

MATRIZ DE PERMISSÃO (perfis reais do banco: tecnico, admin, ti)
    consultar sessões e resumos          : tecnico, admin, ti
    parear dispositivo e registrar leitura: tecnico, admin, ti
    abrir sessão                         : admin, ti
    fechar e cancelar sessão             : admin, ti

    O técnico opera a coleta inteira mas não decide o que fazer com a
    divergência — é o que sustenta RN-14 e RN-15 no nível de permissão, e
    não apenas de código.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from Modulo_06_dados import (
    get_session, BemPatrimonial, InventarioItem, ColetaToken,
    EscopoInventarioEnum, StatusInventarioEnum, StatusItemInventarioEnum, TipoSobraEnum,
    SituacaoBemEnum,
)
from Modulo_05_admin import ConfigService

from .dto import (
    AjusteConfirmado, ClassificacaoLeitura, ContextoColeta, ConviteColeta,
    LeituraRecente, ResultadoAbertura, ResultadoLeitura, ResumoSessao, Aviso,
    CodigoAviso, SeveridadeLeitura,
)
from .excecoes import (
    SessaoNaoEncontradaError, SessaoNaoAbertaError, EscopoConflitanteError,
    AjusteNaoConfirmadoError, TokenInvalidoError, TokenExpiradoError,
    TokenRevogadoError, CodigoIlegivelError, LocalizacaoNaoEncontradaError,
    EscopoFixoError,
)
from .autorizacao import resolver_usuario_autorizado
from .inventario_repo import InventarioRepo
from .localizacao_repo import LocalizacaoRepo
from .patrimonio_service import PatrimonioService

logger = logging.getLogger(__name__)

_HORAS_TOKEN_PADRAO = 12
_DIAS_ALERTA_PADRAO = 7

_SEVERIDADE_POR_CLASSIFICACAO = {
    ClassificacaoLeitura.encontrado:           SeveridadeLeitura.ok,
    ClassificacaoLeitura.ja_conferido:         SeveridadeLeitura.ok,
    ClassificacaoLeitura.divergente_local:     SeveridadeLeitura.atencao,
    ClassificacaoLeitura.sobra_outra_sessao:   SeveridadeLeitura.atencao,
    ClassificacaoLeitura.sobra_fora_escopo:    SeveridadeLeitura.atencao,
    ClassificacaoLeitura.sobra_nao_cadastrado: SeveridadeLeitura.atencao,
    ClassificacaoLeitura.bem_baixado:          SeveridadeLeitura.erro,
    ClassificacaoLeitura.codigo_ilegivel:      SeveridadeLeitura.erro,
}


class InventarioService:
    """Fachada de MOD-07 para sessões de inventário e coleta."""

    def __init__(self):
        self._patrimonio = PatrimonioService()

    # ─── Ciclo de vida da sessão ────────────────────────────────────────────

    def contar_escopo(self, escopo: str, localizacao_id: int | None = None) -> int:
        """
        Conta quantos bens ativos o escopo abrangeria, SEM criar sessão.

        Usada por T-26 na tela de abertura, para avisar antes de abrir uma
        campanha vazia. Exclui bens baixados — nunca entram em sessão
        (RN-12).

        Raises:
            LocalizacaoNaoEncontradaError
        """
        escopo_enum = EscopoInventarioEnum(escopo)
        if escopo_enum == EscopoInventarioEnum.localizacao:
            if localizacao_id is None or not LocalizacaoRepo.buscar_por_id(localizacao_id):
                raise LocalizacaoNaoEncontradaError(
                    f"Localização {localizacao_id} não encontrada."
                )
        return InventarioRepo.contar_escopo(escopo_enum, localizacao_id)

    def abrir_sessao(self, descricao: str, escopo: str, usuario_id: int,
                     localizacao_id: int | None = None) -> ResultadoAbertura:
        """
        Abre sessão e materializa o snapshot (RF-31, AD-19).
        Em transação única:
          1. RN-16 completa: índice único do banco cobre parte; verifica
             aqui: escopo='geral' recusa se QUALQUER sessão aberta;
             escopo='localizacao' recusa se existir sessão geral aberta.
          2. Insere linha em inventario.
          3. Insere em lote inventario_item, um por bem ativo do escopo,
             status='pendente', localizacao_esperada_id COPIADA da lotação
             atual (preserva onde deveria estar caso o bem seja movido
             durante a sessão).
        Bens baixados nunca entram (RN-12).
        Escopo sem bens não impede abertura — retorna CodigoAviso.escopo_vazio
        em avisos; tela deve chamar contar_escopo() antes.
        Raises: EscopoConflitanteError, LocalizacaoNaoEncontradaError, PermissaoNegadaError
        """
        resolver_usuario_autorizado(usuario_id, "abrir_sessao_inventario")
        escopo_enum = EscopoInventarioEnum(escopo)

        if escopo_enum == EscopoInventarioEnum.localizacao:
            if localizacao_id is None or not LocalizacaoRepo.buscar_por_id(localizacao_id):
                raise LocalizacaoNaoEncontradaError(
                    f"Localização {localizacao_id} não encontrada."
                )

        try:
            with get_session() as s:
                if escopo_enum == EscopoInventarioEnum.geral:
                    if InventarioRepo.existe_qualquer_sessao_aberta(s):
                        raise EscopoConflitanteError(
                            "Já existe uma sessão de inventário aberta — feche-a "
                            "antes de abrir uma sessão geral."
                        )
                else:
                    if InventarioRepo.existe_sessao_geral_aberta(s):
                        raise EscopoConflitanteError(
                            "Existe uma sessão geral aberta, que bloqueia "
                            "qualquer outra sessão até ser fechada."
                        )
                    if InventarioRepo.existe_sessao_aberta_na_localizacao(s, localizacao_id):
                        raise EscopoConflitanteError(
                            "Já existe uma sessão de inventário aberta nesta localização."
                        )

                inventario, total = InventarioRepo.criar_sessao_com_snapshot(
                    s, descricao=descricao, escopo=escopo_enum, usuario_id=usuario_id,
                    localizacao_id=localizacao_id,
                )
        except IntegrityError as exc:
            # Corrida entre a checagem acima e o índice único de
            # escopo_aberto — outra estação abriu no mesmo instante.
            raise EscopoConflitanteError(
                "Já existe uma sessão de inventário aberta com escopo conflitante."
            ) from exc

        avisos = ()
        if total == 0:
            avisos = (Aviso(
                codigo=CodigoAviso.escopo_vazio,
                mensagem="O escopo selecionado não tem nenhum bem ativo — "
                         "a sessão foi aberta, mas não há o que conferir.",
            ),)

        logger.info("Sessão de inventário aberta: id=%s escopo=%s total=%s usuario_id=%s",
                    inventario.id, escopo, total, usuario_id)
        return ResultadoAbertura(
            inventario_id=inventario.id, descricao=descricao,
            total_esperado=total, avisos=avisos,
        )

    def listar_sessoes(self, status: str | None = None) -> list:
        """Sessões para o painel de histórico de T-26."""
        status_enum = StatusInventarioEnum(status) if status else None
        return InventarioRepo.listar_sessoes(status_enum)

    def obter_sessao(self, inventario_id: int):
        """Raises: SessaoNaoEncontradaError"""
        inv = InventarioRepo.buscar_sessao(inventario_id)
        if not inv:
            raise SessaoNaoEncontradaError(f"Sessão {inventario_id} não encontrada.")
        return inv

    def resumo_sessao(self, inventario_id: int) -> ResumoSessao:
        """Contagens por status — consulta agregada, sem carregar itens."""
        inv = self.obter_sessao(inventario_id)
        contagem = InventarioRepo.resumo_sessao(inventario_id)
        return ResumoSessao(
            inventario_id=inv.id,
            descricao=inv.descricao,
            escopo=inv.escopo.value,
            localizacao=inv.localizacao.nome_completo if inv.localizacao else None,
            status=inv.status.value,
            aberto_em=inv.aberto_em,
            total_esperado=contagem["total"],
            pendentes=contagem[StatusItemInventarioEnum.pendente.value],
            encontrados=contagem[StatusItemInventarioEnum.encontrado.value],
            divergentes=contagem[StatusItemInventarioEnum.divergente_local.value],
            nao_localizados=contagem[StatusItemInventarioEnum.nao_localizado.value],
            sobras=contagem["sobras"],
        )

    def listar_leituras_recentes(self, inventario_id: int, limite: int = 8) -> list[LeituraRecente]:
        """
        Log "Últimas leituras" de T-26 — reconstruído do banco (itens
        conferidos + sobras), não de estado em memória do processo desktop.
        É a única forma de refletir leituras vindas de um celular pareado:
        essas acontecem inteiramente no processo do ColetaWebService,
        separado do desktop, que só fica sabendo delas por consulta.
        """
        itens = InventarioRepo.listar_conferidos_recentes(inventario_id, limite)
        sobras = InventarioRepo.listar_sobras_recentes(inventario_id, limite)

        leituras = [
            LeituraRecente(
                tombo=item.bem.tombo, descricao_bem=item.bem.descricao,
                mensagem=("Conferido — na localização esperada." if item.status == StatusItemInventarioEnum.encontrado
                           else "Encontrado em local diferente do esperado."),
                severidade=(SeveridadeLeitura.ok if item.status == StatusItemInventarioEnum.encontrado
                            else SeveridadeLeitura.atencao),
                quando=item.conferido_em,
            )
            for item in itens
        ] + [
            LeituraRecente(
                tombo=None, descricao_bem=sobra.codigo_lido,
                mensagem=("Código não corresponde a nenhum bem cadastrado." if sobra.tipo == TipoSobraEnum.nao_cadastrado
                           else "Bem fora do escopo desta sessão."),
                severidade=SeveridadeLeitura.atencao,
                quando=sobra.registrado_em,
            )
            for sobra in sobras
        ]
        leituras.sort(key=lambda l: l.quando, reverse=True)
        return leituras[:limite]

    def cancelar_sessao(self, inventario_id: int, motivo: str, usuario_id: int):
        """
        Cancela sem aplicar ajuste, revoga tokens, libera escopo (vira NULL).
        Leituras já registradas permanecem como registro histórico.
        Raises: SessaoNaoEncontradaError, SessaoNaoAbertaError, PermissaoNegadaError
        """
        resolver_usuario_autorizado(usuario_id, "cancelar_sessao_inventario")
        inv = self.obter_sessao(inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {inventario_id} não está aberta.")

        with get_session() as s:
            InventarioRepo.revogar_tokens_sessao(s, inventario_id)
            InventarioRepo.remover_convite(s, inventario_id)
            InventarioRepo.cancelar_sessao(s, inventario_id, usuario_id)

        logger.info("Sessão de inventário cancelada: id=%s motivo=%r usuario_id=%s",
                    inventario_id, motivo, usuario_id)

    def fechar_sessao(self, inventario_id: int,
                      ajustes: list[AjusteConfirmado],
                      usuario_id: int) -> ResumoSessao:
        """
        Fecha e aplica ajustes confirmados (RF-34). Transação única:
          1. Exige decisão para TODA divergência — sem ajuste correspondente
             levanta AjusteNaoConfirmadoError (RN-14).
          2. aplicar=True: atualiza localização do bem + grava
             movimentacao_bem tipo='ajuste_inventario' com inventario_id.
          3. Pendentes → 'nao_localizado'; bens correspondentes →
             situacao='em_apuracao' (RN-15, jamais 'baixado').
          4. Revoga todos tokens (RN-19).
          5. status='finalizado', libera escopo.
        Sobras não geram ação automática — ficam no relatório.
        Raises: SessaoNaoEncontradaError, SessaoNaoAbertaError,
                AjusteNaoConfirmadoError, PermissaoNegadaError
        """
        resolver_usuario_autorizado(usuario_id, "fechar_sessao_inventario")
        inv = self.obter_sessao(inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {inventario_id} não está aberta.")

        divergentes = InventarioRepo.listar_itens(
            inventario_id, StatusItemInventarioEnum.divergente_local
        )
        ids_divergentes = {item.id for item in divergentes}
        ids_confirmados = {ajuste.inventario_item_id for ajuste in ajustes}
        faltando = ids_divergentes - ids_confirmados
        if faltando:
            raise AjusteNaoConfirmadoError(
                f"{len(faltando)} divergência(s) sem decisão de ajuste — "
                "confirme todas antes de fechar a sessão."
            )

        with get_session() as s:
            for ajuste in ajustes:
                item = s.get(InventarioItem, ajuste.inventario_item_id)
                if (not item or item.inventario_id != inventario_id
                        or item.status != StatusItemInventarioEnum.divergente_local):
                    continue
                InventarioRepo.aplicar_ajuste(
                    s, item, ajuste.aplicar, ajuste.observacao, usuario_id
                )

            InventarioRepo.marcar_pendentes_como_nao_localizado(s, inventario_id)
            InventarioRepo.revogar_tokens_sessao(s, inventario_id)
            InventarioRepo.remover_convite(s, inventario_id)
            InventarioRepo.finalizar_sessao(s, inventario_id, usuario_id)

        logger.info("Sessão de inventário fechada: id=%s usuario_id=%s", inventario_id, usuario_id)
        return self.resumo_sessao(inventario_id)

    # ─── Convite de pareamento (QR fixo da sessão) ──────────────────────────

    def obter_convite(self, inventario_id: int, usuario_id: int) -> str:
        """
        Devolve a URL do QR fixo da sessão (RF-36 revisado). Idempotente por
        natureza: sempre a MESMA URL para a mesma sessão, gerada uma única
        vez — remontar a tela de coleta ou trocar a localização de bipagem
        do operador na estação não cria nada novo aqui. O convite em si não
        representa nenhum aparelho: quem cria o ColetaToken real é
        registrar_dispositivo, chamado a partir do celular.
        Raises: SessaoNaoEncontradaError, SessaoNaoAbertaError
        """
        resolver_usuario_autorizado(usuario_id)
        inv = self.obter_sessao(inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {inventario_id} não está aberta.")

        convite = InventarioRepo.buscar_convite_sessao(inventario_id)
        if not convite:
            with get_session() as s:
                convite = InventarioRepo.criar_convite(s, inventario_id=inventario_id, usuario_id=usuario_id)

        host = ConfigService.get("coleta_host")
        porta = ConfigService.get("coleta_porta")
        return f"http://{host}:{porta}/parear?token={convite.token}"

    def resolver_convite(self, token: str) -> ConviteColeta:
        """
        Valida o convite escaneado e monta os dados do formulário de cadastro
        do celular. Se a sessão for de escopo único, a localização já vem
        fixada (o formulário não pergunta nada); se for geral, devolve as
        opções para o próprio celular escolher.
        Raises: TokenInvalidoError, SessaoNaoAbertaError
        """
        convite = InventarioRepo.buscar_convite_por_token(token)
        if not convite:
            raise TokenInvalidoError("Convite inválido.")
        inv = self.obter_sessao(convite.inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {convite.inventario_id} não está mais aberta.")
        return self._dados_localizacao_sessao(inv)

    def opcoes_troca_localizacao(self, contexto: ContextoColeta) -> ConviteColeta:
        """Mesma forma de dados de resolver_convite, a partir de um contexto já
        pareado — usado pelo GET /localizacao para montar o formulário de
        troca de sala (RN-19, só sessões de escopo geral têm o que trocar).
        Raises: SessaoNaoAbertaError
        """
        inv = self.obter_sessao(contexto.inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {contexto.inventario_id} não está mais aberta.")
        return self._dados_localizacao_sessao(inv)

    @staticmethod
    def _dados_localizacao_sessao(inv) -> ConviteColeta:
        if inv.escopo == EscopoInventarioEnum.localizacao and inv.localizacao:
            return ConviteColeta(
                inventario_id=inv.id, descricao_sessao=inv.descricao,
                localizacao_fixa_id=inv.localizacao.id,
                localizacao_fixa=inv.localizacao.nome_completo,
            )
        opcoes = tuple((loc.id, loc.nome_completo) for loc in LocalizacaoRepo.listar())
        return ConviteColeta(inventario_id=inv.id, descricao_sessao=inv.descricao, opcoes_localizacao=opcoes)

    def buscar_dispositivo_conhecido(self, inventario_id: int, dispositivo_id: str) -> ColetaToken | None:
        """Token válido já existente para esse aparelho (mesmo dispositivo_id)
        nesta sessão, se houver — usado pelo GET /parear para reconectar sem
        formulário nem token novo."""
        token = InventarioRepo.buscar_token_dispositivo(inventario_id, dispositivo_id)
        return token if token and token.valido else None

    def registrar_dispositivo(self, convite_token: str, localizacao_id: int | None,
                              dispositivo_label: str | None, dispositivo_id: str) -> str:
        """
        Confirma o cadastro de um aparelho a partir do convite da sessão
        (RF-36 revisado) — chamado pelo POST /parear do ColetaWebService,
        sem usuário autenticado; a autoria (usuario_id do ColetaToken) vem
        de quem gerou o convite no desktop (T-26).

        Sessão de escopo único: ignora o localizacao_id recebido e usa
        sempre o da sessão (fecha a brecha de um cliente forjar outra sala).
        Sessão de escopo geral: valida o localizacao_id recebido.

        Idempotente por dispositivo_id: se este aparelho já tiver um token
        válido nesta sessão, devolve o mesmo token em vez de duplicar.
        Raises: TokenInvalidoError, SessaoNaoAbertaError, LocalizacaoNaoEncontradaError
        """
        convite = InventarioRepo.buscar_convite_por_token(convite_token)
        if not convite:
            raise TokenInvalidoError("Convite inválido.")
        inv = self.obter_sessao(convite.inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {convite.inventario_id} não está mais aberta.")

        if inv.escopo == EscopoInventarioEnum.localizacao:
            localizacao_id = inv.localizacao_id
        elif not localizacao_id or not LocalizacaoRepo.buscar_por_id(localizacao_id):
            raise LocalizacaoNaoEncontradaError("Selecione uma localização válida.")

        existente = InventarioRepo.buscar_token_dispositivo(convite.inventario_id, dispositivo_id)
        if existente and existente.valido:
            return existente.token

        horas = float(ConfigService.get("coleta_token_horas") or _HORAS_TOKEN_PADRAO)
        with get_session() as s:
            token = InventarioRepo.criar_token(
                s, inventario_id=convite.inventario_id, localizacao_conferida_id=localizacao_id,
                usuario_id=convite.usuario_id, horas_validade=horas,
                dispositivo_label=dispositivo_label, dispositivo_id=dispositivo_id,
            )

        logger.info("Dispositivo cadastrado: inventario_id=%s localizacao_id=%s dispositivo=%r",
                    convite.inventario_id, localizacao_id, dispositivo_label)
        return token.token

    def trocar_localizacao(self, contexto: ContextoColeta, localizacao_id: int) -> None:
        """
        Atualiza a sala de leitura de um aparelho já pareado, sem revogar ou
        criar token — só sessões de escopo geral: numa sessão de escopo
        único a sala é fixa por definição.
        Raises: SessaoNaoAbertaError, EscopoFixoError, LocalizacaoNaoEncontradaError
        """
        inv = self.obter_sessao(contexto.inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {contexto.inventario_id} não está mais aberta.")
        if inv.escopo == EscopoInventarioEnum.localizacao:
            raise EscopoFixoError(f"Esta sessão está fixada em {inv.localizacao.nome_completo}.")
        if not LocalizacaoRepo.buscar_por_id(localizacao_id):
            raise LocalizacaoNaoEncontradaError(f"Localização {localizacao_id} não encontrada.")

        with get_session() as s:
            InventarioRepo.atualizar_localizacao_token(s, contexto.token_id, localizacao_id)

    def resolver_token(self, token: str) -> ContextoColeta:
        """
        Valida token, devolve contexto. Chamado pelo serviço HTTP a cada
        requisição. Ordem: existência, revogação, expiração, sessão
        continua aberta (última importa: fechamento revoga mas requisição
        em voo pode chegar depois).
        Raises: TokenInvalidoError, TokenRevogadoError, TokenExpiradoError, SessaoNaoAbertaError
        """
        coleta = InventarioRepo.buscar_token(token)
        if not coleta:
            raise TokenInvalidoError("Token inválido.")
        if coleta.revogado:
            raise TokenRevogadoError("Token revogado.")
        if coleta.expira_em <= datetime.utcnow():
            raise TokenExpiradoError("Token expirado.")
        if coleta.inventario.status != StatusInventarioEnum.aberto:
            raise SessaoNaoAbertaError(
                f"Sessão {coleta.inventario_id} não está mais aberta."
            )

        return ContextoColeta(
            inventario_id=coleta.inventario_id,
            localizacao_id=coleta.localizacao_conferida_id,
            usuario_id=coleta.usuario_id,
            origem="movel",
            token_id=coleta.id,
            dispositivo_label=coleta.dispositivo_label,
        )

    def revogar_tokens(self, inventario_id: int, usuario_id: int) -> int:
        """Revoga todos tokens da sessão, devolve quantos. Ação manual em T-26
        (celular perdido/emprestado). Revogação é lógica."""
        resolver_usuario_autorizado(usuario_id)
        self.obter_sessao(inventario_id)
        with get_session() as s:
            total = InventarioRepo.revogar_tokens_sessao(s, inventario_id)
        logger.info("Tokens revogados manualmente: inventario_id=%s total=%s usuario_id=%s",
                    inventario_id, total, usuario_id)
        return total

    def listar_dispositivos(self, inventario_id: int, usuario_id: int) -> list:
        """Dispositivos atualmente pareados (não revogados, não expirados) — painel de T-26."""
        resolver_usuario_autorizado(usuario_id)
        self.obter_sessao(inventario_id)
        tokens = InventarioRepo.listar_tokens_sessao(inventario_id)
        return [t for t in tokens if t.valido]

    # ─── Coleta ─────────────────────────────────────────────────────────────

    def registrar_leitura(self, codigo_lido: str,
                          contexto: ContextoColeta) -> ResultadoLeitura:
        """
        NÚCLEO DO MÓDULO (RF-32, RF-33). Ponto de entrada único das três
        vias de coleta.
        ÁRVORE DE DECISÃO (ERS §3.2), nesta ordem exata:
          1. resolver_codigo falha → codigo_ilegivel, nada gravado, erro
          2. tombo não existe → sobra_nao_cadastrado em inventario_sobra, atenção
          3. bem situacao='baixado' → bem_baixado, nada gravado, erro
          4. item já conferido → ja_conferido, nada gravado, ok
             (idempotência via UNIQUE(inventario_id, bem_id))
          5. item na localizacao_esperada == contexto → encontrado, ok
          6. item em localização diferente → divergente_local, grava
             localizacao_encontrada_id, atenção; NÃO altera cadastro
             (RN-14, só no fechamento)
          7. bem em OUTRA sessão aberta → sobra_outra_sessao (RN-18): grava
             sobra na sessão do contexto E marca divergente_local na sessão
             de origem
          8. bem cadastrado fora de qualquer sessão → sobra_fora_escopo, atenção
        Transação única. Colisão de UNIQUE por leitura simultânea = caso 4.
        NUNCA levanta exceção por leitura inesperada (RNF-13).
        Raises: SessaoNaoEncontradaError, SessaoNaoAbertaError
        """
        resolver_usuario_autorizado(contexto.usuario_id)

        inv = self.obter_sessao(contexto.inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(f"Sessão {contexto.inventario_id} não está aberta.")

        # Passo 1 — resolução do código. RNF-13: falha de leitura nunca sobe
        # como exceção da operação, só como resultado erro/codigo_ilegivel.
        try:
            tombo = self._patrimonio.resolver_codigo(codigo_lido)
        except CodigoIlegivelError as exc:
            return self._resultado_leitura(
                ClassificacaoLeitura.codigo_ilegivel, codigo_lido, mensagem=str(exc),
            )

        loc_atual = LocalizacaoRepo.buscar_por_id(contexto.localizacao_id)
        nome_loc_atual = loc_atual.nome_completo if loc_atual else None

        with get_session() as s:
            bem = (s.query(BemPatrimonial)
                   .filter(func.lower(func.trim(BemPatrimonial.tombo)) == tombo.strip().lower())
                   .first())

            # Passo 2 — tombo não cadastrado
            if not bem:
                InventarioRepo.criar_sobra(
                    s, inventario_id=contexto.inventario_id, codigo_lido=codigo_lido,
                    tipo=TipoSobraEnum.nao_cadastrado, localizacao_id=contexto.localizacao_id,
                    usuario_id=contexto.usuario_id,
                )
                total_esperado, total_conferido = self._progresso(s, contexto.inventario_id)
                return self._resultado_leitura(
                    ClassificacaoLeitura.sobra_nao_cadastrado, codigo_lido,
                    mensagem=f"Código '{codigo_lido}' não corresponde a nenhum bem cadastrado.",
                    localizacao_lida=nome_loc_atual,
                    total_esperado=total_esperado, total_conferido=total_conferido,
                )

            # Passo 3 — bem baixado
            if bem.situacao == SituacaoBemEnum.baixado:
                return self._resultado_leitura(
                    ClassificacaoLeitura.bem_baixado, codigo_lido,
                    tombo=bem.tombo, descricao_bem=bem.descricao,
                    localizacao_lida=nome_loc_atual,
                    mensagem=f"Bem {bem.tombo} está baixado — não pertence a nenhuma sessão de inventário.",
                )

            item = InventarioRepo.buscar_item(s, contexto.inventario_id, bem.id)

            if item:
                # Passo 4 — já conferido nesta sessão
                if item.status != StatusItemInventarioEnum.pendente:
                    total_esperado, total_conferido = self._progresso(s, contexto.inventario_id)
                    return self._resultado_leitura(
                        ClassificacaoLeitura.ja_conferido, codigo_lido,
                        tombo=bem.tombo, descricao_bem=bem.descricao,
                        localizacao_lida=nome_loc_atual,
                        conferido_em=item.conferido_em,
                        conferido_por=item.conferido_por_usuario.nome if item.conferido_por_usuario else None,
                        mensagem=f"Bem {bem.tombo} já foi conferido nesta sessão.",
                        total_esperado=total_esperado, total_conferido=total_conferido,
                    )

                loc_esperada = LocalizacaoRepo.buscar_por_id(item.localizacao_esperada_id)
                nome_loc_esperada = loc_esperada.nome_completo if loc_esperada else None

                # Passo 5 — encontrado na localização esperada
                if item.localizacao_esperada_id == contexto.localizacao_id:
                    InventarioRepo.marcar_encontrado(s, item, contexto.usuario_id)
                    total_esperado, total_conferido = self._progresso(s, contexto.inventario_id)
                    return self._resultado_leitura(
                        ClassificacaoLeitura.encontrado, codigo_lido,
                        tombo=bem.tombo, descricao_bem=bem.descricao,
                        localizacao_esperada=nome_loc_esperada, localizacao_lida=nome_loc_atual,
                        mensagem=f"Bem {bem.tombo} conferido — na localização esperada.",
                        total_esperado=total_esperado, total_conferido=total_conferido,
                    )

                # Passo 6 — divergente de local
                InventarioRepo.marcar_divergente(s, item, contexto.localizacao_id, contexto.usuario_id)
                total_esperado, total_conferido = self._progresso(s, contexto.inventario_id)
                return self._resultado_leitura(
                    ClassificacaoLeitura.divergente_local, codigo_lido,
                    tombo=bem.tombo, descricao_bem=bem.descricao,
                    localizacao_esperada=nome_loc_esperada, localizacao_lida=nome_loc_atual,
                    mensagem=f"Bem {bem.tombo} encontrado em local diferente do esperado "
                             f"({nome_loc_esperada}).",
                    total_esperado=total_esperado, total_conferido=total_conferido,
                )

            # Passo 7 — bem pertence a outra sessão aberta (RN-18)
            outro_item = InventarioRepo.buscar_item_pendente_em_outra_sessao(
                s, bem.id, contexto.inventario_id
            )
            if outro_item:
                InventarioRepo.marcar_divergente(
                    s, outro_item, contexto.localizacao_id, contexto.usuario_id
                )
                InventarioRepo.criar_sobra(
                    s, inventario_id=contexto.inventario_id, codigo_lido=codigo_lido,
                    tipo=TipoSobraEnum.fora_escopo, localizacao_id=contexto.localizacao_id,
                    usuario_id=contexto.usuario_id,
                    descricao_livre=f"Bem pertence à sessão de inventário {outro_item.inventario_id}.",
                )
                total_esperado, total_conferido = self._progresso(s, contexto.inventario_id)
                return self._resultado_leitura(
                    ClassificacaoLeitura.sobra_outra_sessao, codigo_lido,
                    tombo=bem.tombo, descricao_bem=bem.descricao,
                    localizacao_lida=nome_loc_atual,
                    mensagem=f"Bem {bem.tombo} pertence a outra sessão de inventário em andamento.",
                    total_esperado=total_esperado, total_conferido=total_conferido,
                )

            # Passo 8 — bem cadastrado, fora de qualquer sessão aberta
            InventarioRepo.criar_sobra(
                s, inventario_id=contexto.inventario_id, codigo_lido=codigo_lido,
                tipo=TipoSobraEnum.fora_escopo, localizacao_id=contexto.localizacao_id,
                usuario_id=contexto.usuario_id,
            )
            total_esperado, total_conferido = self._progresso(s, contexto.inventario_id)
            return self._resultado_leitura(
                ClassificacaoLeitura.sobra_fora_escopo, codigo_lido,
                tombo=bem.tombo, descricao_bem=bem.descricao,
                localizacao_lida=nome_loc_atual,
                mensagem=f"Bem {bem.tombo} está fora do escopo desta sessão.",
                total_esperado=total_esperado, total_conferido=total_conferido,
            )

    def listar_itens(self, inventario_id: int, status: str | None = None) -> list:
        """Itens filtráveis por status."""
        status_enum = StatusItemInventarioEnum(status) if status else None
        return InventarioRepo.listar_itens(inventario_id, status_enum)

    def listar_sobras(self, inventario_id: int) -> list:
        return InventarioRepo.listar_sobras(inventario_id)

    def descartar_sobra(self, sobra_id: int, usuario_id: int) -> None:
        """Única exclusão física do módulo — sobra não é fato patrimonial.
        Raises: SessaoNaoAbertaError, PermissaoNegadaError"""
        resolver_usuario_autorizado(usuario_id)
        sobra = InventarioRepo.buscar_sobra(sobra_id)
        if not sobra:
            return
        inv = self.obter_sessao(sobra.inventario_id)
        if not inv.aberta:
            raise SessaoNaoAbertaError(
                f"Sessão {sobra.inventario_id} não está mais aberta."
            )
        InventarioRepo.excluir_sobra(sobra_id)
        logger.info("Sobra descartada: id=%s inventario_id=%s usuario_id=%s",
                    sobra_id, sobra.inventario_id, usuario_id)

    # ─── Relatório ──────────────────────────────────────────────────────────

    def gerar_relatorio(self, inventario_id: int, usuario_id: int) -> str:
        """Gera XLSX via MOD-03, abas: resumo, encontrados, divergências,
        não localizados, sobras. Raises: SessaoNaoEncontradaError"""
        resolver_usuario_autorizado(usuario_id)
        inv = self.obter_sessao(inventario_id)
        resumo = self.resumo_sessao(inventario_id)
        itens = InventarioRepo.listar_itens(inventario_id)
        sobras = InventarioRepo.listar_sobras(inventario_id)

        from Modulo_03_relatorios.xlsx_builder import XlsxBuilder
        caminho = XlsxBuilder.relatorio_inventario(inv, resumo, itens, sobras)

        logger.info("Relatório de inventário gerado: inventario_id=%s usuario_id=%s",
                    inventario_id, usuario_id)
        return str(caminho)

    def enviar_relatorio(self, inventario_id: int, usuario_id: int) -> None:
        """
        Gera o mesmo XLSX de gerar_relatorio e envia por e-mail (T-27, RF-35
        — "divergências de sessão" é reimpressão sob demanda de uma sessão
        específica, escolhida numa lista).

        Raises: SessaoNaoEncontradaError, PermissaoNegadaError
        """
        inv = self.obter_sessao(inventario_id)
        caminho = self.gerar_relatorio(inventario_id, usuario_id)

        from pathlib import Path
        from Modulo_04_notificacoes.gmail_client import GmailClient
        corpo_html = f"""
        <div style="font-family: Arial, sans-serif; color: #3d3d3a;">
            <h2 style="color: #1F5F5B;">SCE — Divergências de sessão de inventário</h2>
            <p>Sessão #{inv.id} — {inv.descricao}.</p>
            <p style="color: #888780; font-size: 12px;">
                Relatório gerado automaticamente pelo Sistema de Controle de
                Estoque — Centro de Uro-Nefrologia.
            </p>
        </div>
        """
        GmailClient.enviar(f"SCE — Divergências: sessão #{inv.id}", corpo_html, anexos=[Path(caminho)])

    def alertar_sessoes_antigas(self) -> list:
        """Sessões abertas há mais tempo que inventario_alerta_dias (R-13)."""
        dias = int(ConfigService.get("inventario_alerta_dias") or _DIAS_ALERTA_PADRAO)
        return InventarioRepo.sessoes_abertas_ha_mais_de(dias)

    # ─── Interno ──────────────────────────────────────────────────────────────

    @staticmethod
    def _progresso(session, inventario_id: int) -> tuple[int, int]:
        """
        Contagem viva de progresso, na MESMA transação da leitura em curso
        — lida com o estado recém-gravado, ainda não commitado, em vez de
        uma segunda conexão que não o enxergaria.

        flush() explícito é necessário: a sessão do projeto usa
        autoflush=False (database.py), então a mutação de item.status feita
        por marcar_encontrado/marcar_divergente logo antes desta chamada
        fica só em memória até o flush — sem ele, esta contagem SELECT
        ainda vê o estado antigo, e a resposta de registrar_leitura chega
        com progresso "um passo atrás" (bug relatado: 0/x após a primeira
        leitura).
        """
        session.flush()
        total_esperado = (session.query(func.count(InventarioItem.id))
                          .filter(InventarioItem.inventario_id == inventario_id)
                          .scalar() or 0)
        total_conferido = (session.query(func.count(InventarioItem.id))
                           .filter(InventarioItem.inventario_id == inventario_id,
                                   InventarioItem.status.in_([
                                       StatusItemInventarioEnum.encontrado,
                                       StatusItemInventarioEnum.divergente_local,
                                   ]))
                           .scalar() or 0)
        return total_esperado, total_conferido

    @staticmethod
    def _resultado_leitura(classificacao: ClassificacaoLeitura, codigo_lido: str,
                           mensagem: str, tombo: str | None = None,
                           descricao_bem: str | None = None,
                           localizacao_esperada: str | None = None,
                           localizacao_lida: str | None = None,
                           conferido_em=None, conferido_por: str | None = None,
                           total_esperado: int = 0, total_conferido: int = 0) -> ResultadoLeitura:
        return ResultadoLeitura(
            classificacao=classificacao,
            severidade=_SEVERIDADE_POR_CLASSIFICACAO[classificacao],
            mensagem=mensagem,
            codigo_lido=codigo_lido,
            tombo=tombo,
            descricao_bem=descricao_bem,
            localizacao_esperada=localizacao_esperada,
            localizacao_lida=localizacao_lida,
            conferido_em=conferido_em,
            conferido_por=conferido_por,
            total_esperado=total_esperado,
            total_conferido=total_conferido,
        )
