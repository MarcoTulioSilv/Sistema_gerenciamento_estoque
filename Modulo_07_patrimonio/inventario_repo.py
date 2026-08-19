"""
MOD-07 · Modulo_07_patrimonio · inventario_repo.py
Repositório de sessões de inventário, itens, sobras e tokens de coleta —
acesso via MOD-06.

CONVENÇÃO DE TRANSAÇÃO
    Métodos que recebem `session` como primeiro parâmetro participam da
    transação já aberta pelo chamador (mesmo padrão de BemRepo.criar/baixar)
    — é assim que InventarioService compõe o ciclo de vida da sessão e o
    fechamento com ajuste em uma única transação. Métodos sem `session`
    abrem a própria (get_session/get_read_session).
"""
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from Modulo_06_dados import (
    get_session, get_read_session,
    Inventario, InventarioItem, InventarioSobra, ColetaToken,
    BemPatrimonial, MovimentacaoBem,
    EscopoInventarioEnum, StatusInventarioEnum, StatusItemInventarioEnum,
    TipoSobraEnum, SituacaoBemEnum, TipoMovimentacaoBemEnum,
)

logger = logging.getLogger(__name__)

_TOKEN_BYTES = 32  # secrets.token_urlsafe(32) -> 43 caracteres, cabe em CHAR(43)


class InventarioRepo:

    # ─── Sessão — leitura ───────────────────────────────────────────────────

    @staticmethod
    def contar_escopo(escopo: EscopoInventarioEnum, localizacao_id: int | None = None) -> int:
        with get_read_session() as s:
            q = s.query(func.count(BemPatrimonial.id)).filter(
                BemPatrimonial.situacao == SituacaoBemEnum.ativo
            )
            if escopo == EscopoInventarioEnum.localizacao:
                q = q.filter(BemPatrimonial.localizacao_id == localizacao_id)
            return q.scalar() or 0

    @staticmethod
    def listar_sessoes(status: StatusInventarioEnum | None = None) -> list[Inventario]:
        with get_read_session() as s:
            q = s.query(Inventario).options(
                joinedload(Inventario.localizacao),
                joinedload(Inventario.aberto_por_usuario),
                joinedload(Inventario.finalizado_por_usuario),
            )
            if status:
                q = q.filter(Inventario.status == status)
            itens = q.order_by(Inventario.aberto_em.desc()).all()
            s.expunge_all()
            return itens

    @staticmethod
    def buscar_sessao(inventario_id: int) -> Inventario | None:
        with get_read_session() as s:
            obj = (s.query(Inventario)
                   .options(joinedload(Inventario.localizacao))
                   .filter(Inventario.id == inventario_id)
                   .first())
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def resumo_sessao(inventario_id: int) -> dict[str, int]:
        """
        Contagens por status em consulta agregada — sem carregar os itens,
        uma sessão pode ter centenas de bens no snapshot.
        """
        with get_read_session() as s:
            linhas = (
                s.query(InventarioItem.status, func.count(InventarioItem.id))
                .filter(InventarioItem.inventario_id == inventario_id)
                .group_by(InventarioItem.status)
                .all()
            )
            contagem = {status.value: 0 for status in StatusItemInventarioEnum}
            for status, total in linhas:
                contagem[status.value] = total
            contagem["sobras"] = (
                s.query(func.count(InventarioSobra.id))
                .filter(InventarioSobra.inventario_id == inventario_id)
                .scalar() or 0
            )
            contagem["total"] = sum(
                v for k, v in contagem.items() if k != "sobras"
            )
            return contagem

    @staticmethod
    def sessoes_abertas_ha_mais_de(dias: int) -> list[Inventario]:
        limite = datetime.utcnow() - timedelta(days=dias)
        with get_read_session() as s:
            itens = (s.query(Inventario)
                     .options(joinedload(Inventario.localizacao))
                     .filter(Inventario.status == StatusInventarioEnum.aberto,
                             Inventario.aberto_em <= limite)
                     .all())
            s.expunge_all()
            return itens

    # ─── Sessão — escrita (participa da transação do chamador) ─────────────

    @staticmethod
    def existe_sessao_geral_aberta(session) -> bool:
        return session.query(Inventario).filter(
            Inventario.status == StatusInventarioEnum.aberto,
            Inventario.escopo == EscopoInventarioEnum.geral,
        ).first() is not None

    @staticmethod
    def existe_qualquer_sessao_aberta(session) -> bool:
        return session.query(Inventario).filter(
            Inventario.status == StatusInventarioEnum.aberto,
        ).first() is not None

    @staticmethod
    def existe_sessao_aberta_na_localizacao(session, localizacao_id: int) -> bool:
        """
        Complementa o índice único de escopo_aberto com uma checagem
        amigável: duas sessões na MESMA localização colidiriam no banco
        (IntegrityError), mas é melhor recusar aqui com mensagem clara.
        """
        return session.query(Inventario).filter(
            Inventario.status == StatusInventarioEnum.aberto,
            Inventario.localizacao_id == localizacao_id,
        ).first() is not None

    @staticmethod
    def criar_sessao_com_snapshot(session, descricao: str, escopo: EscopoInventarioEnum,
                                   usuario_id: int, localizacao_id: int | None = None) -> tuple[Inventario, int]:
        """
        Cria a sessão e materializa o snapshot na mesma transação (RF-31,
        AD-19). localizacao_esperada_id é copiada do bem no instante da
        abertura — se o bem for movimentado durante a sessão, o snapshot
        preserva onde ele deveria estar quando a sessão começou.

        Devolve (inventario, total_itens) — o chamador precisa do total
        para montar ResultadoAbertura sem uma segunda consulta.
        """
        inventario = Inventario(
            descricao=descricao,
            escopo=escopo,
            localizacao_id=localizacao_id,
            aberto_por=usuario_id,
        )
        session.add(inventario)
        session.flush()  # gera inventario.id

        q = session.query(BemPatrimonial.id, BemPatrimonial.localizacao_id).filter(
            BemPatrimonial.situacao == SituacaoBemEnum.ativo
        )
        if escopo == EscopoInventarioEnum.localizacao:
            q = q.filter(BemPatrimonial.localizacao_id == localizacao_id)

        linhas = q.all()
        for bem_id, loc_id in linhas:
            session.add(InventarioItem(
                inventario_id=inventario.id,
                bem_id=bem_id,
                localizacao_esperada_id=loc_id,
                status=StatusItemInventarioEnum.pendente,
            ))
        session.flush()

        session.expunge(inventario)
        return inventario, len(linhas)

    @staticmethod
    def cancelar_sessao(session, inventario_id: int, usuario_id: int) -> None:
        inv = session.get(Inventario, inventario_id)
        if inv:
            inv.status = StatusInventarioEnum.cancelado
            inv.finalizado_em = datetime.utcnow()
            inv.finalizado_por = usuario_id

    @staticmethod
    def finalizar_sessao(session, inventario_id: int, usuario_id: int) -> None:
        inv = session.get(Inventario, inventario_id)
        if inv:
            inv.status = StatusInventarioEnum.finalizado
            inv.finalizado_em = datetime.utcnow()
            inv.finalizado_por = usuario_id

    # ─── Itens — leitura ─────────────────────────────────────────────────────

    @staticmethod
    def listar_itens(inventario_id: int, status: StatusItemInventarioEnum | None = None) -> list[InventarioItem]:
        with get_read_session() as s:
            q = (s.query(InventarioItem)
                 .options(
                     joinedload(InventarioItem.bem),
                     joinedload(InventarioItem.localizacao_esperada),
                     joinedload(InventarioItem.localizacao_encontrada),
                     joinedload(InventarioItem.conferido_por_usuario),
                 )
                 .filter(InventarioItem.inventario_id == inventario_id))
            if status:
                q = q.filter(InventarioItem.status == status)
            itens = q.order_by(InventarioItem.id).all()
            s.expunge_all()
            return itens

    # ─── Itens — escrita (participa da transação do chamador) ──────────────

    @staticmethod
    def buscar_item(session, inventario_id: int, bem_id: int) -> InventarioItem | None:
        """Item do snapshot da PRÓPRIA sessão do contexto — passo 4/5/6 da árvore."""
        return (session.query(InventarioItem)
                .filter(InventarioItem.inventario_id == inventario_id,
                        InventarioItem.bem_id == bem_id)
                .first())

    @staticmethod
    def buscar_item_pendente_em_outra_sessao(session, bem_id: int,
                                              exceto_inventario_id: int) -> InventarioItem | None:
        """
        RN-18: bem pertence ao snapshot de OUTRA sessão aberta, ainda não
        conferido lá. Usada no passo 7 da árvore de decisão.
        """
        return (session.query(InventarioItem)
                .join(Inventario, Inventario.id == InventarioItem.inventario_id)
                .filter(InventarioItem.bem_id == bem_id,
                        InventarioItem.inventario_id != exceto_inventario_id,
                        InventarioItem.status == StatusItemInventarioEnum.pendente,
                        Inventario.status == StatusInventarioEnum.aberto)
                .first())

    @staticmethod
    def marcar_encontrado(session, item: InventarioItem, usuario_id: int) -> None:
        item.status = StatusItemInventarioEnum.encontrado
        item.conferido_em = datetime.utcnow()
        item.conferido_por = usuario_id

    @staticmethod
    def marcar_divergente(session, item: InventarioItem, localizacao_encontrada_id: int,
                          usuario_id: int) -> None:
        item.status = StatusItemInventarioEnum.divergente_local
        item.localizacao_encontrada_id = localizacao_encontrada_id
        item.conferido_em = datetime.utcnow()
        item.conferido_por = usuario_id

    @staticmethod
    def aplicar_ajuste(session, item: InventarioItem, aplicar: bool,
                       observacao: str | None, usuario_id: int) -> None:
        """
        Fechamento (RN-14): aplicar=True move o bem para a localização
        encontrada e grava movimentacao_bem vinculada à sessão que originou
        o ajuste — não reaproveita BemRepo.transferir, que não marca
        inventario_id. aplicar=False mantém o cadastro; a observação
        registra a decisão para auditoria.
        """
        if aplicar:
            bem = session.get(BemPatrimonial, item.bem_id)
            origem_id = bem.localizacao_id
            bem.localizacao_id = item.localizacao_encontrada_id
            session.add(MovimentacaoBem(
                bem_id=bem.id,
                tipo=TipoMovimentacaoBemEnum.ajuste_inventario,
                localizacao_origem_id=origem_id,
                localizacao_destino_id=item.localizacao_encontrada_id,
                inventario_id=item.inventario_id,
                usuario_id=usuario_id,
                data_hora=datetime.utcnow(),
            ))
            item.observacao = observacao
        else:
            item.observacao = observacao or "Divergência mantida — ajuste não aplicado."

    @staticmethod
    def marcar_pendentes_como_nao_localizado(session, inventario_id: int) -> list[int]:
        """
        Bulk: pendentes da sessão viram nao_localizado (RN-15) e os bens
        correspondentes vão para em_apuracao — nunca baixado. Filtra por
        situacao=ativo porque um bem pode ter sido baixado por outra via
        durante a sessão, e nesse caso não deve ser reclassificado aqui.
        Devolve os bem_id afetados, para o serviço registrar no log.
        """
        pendentes = (session.query(InventarioItem)
                     .filter(InventarioItem.inventario_id == inventario_id,
                             InventarioItem.status == StatusItemInventarioEnum.pendente)
                     .all())
        bem_ids = [item.bem_id for item in pendentes]
        for item in pendentes:
            item.status = StatusItemInventarioEnum.nao_localizado
        if bem_ids:
            (session.query(BemPatrimonial)
             .filter(BemPatrimonial.id.in_(bem_ids),
                     BemPatrimonial.situacao == SituacaoBemEnum.ativo)
             .update({BemPatrimonial.situacao: SituacaoBemEnum.em_apuracao},
                     synchronize_session=False))
        return bem_ids

    # ─── Sobras ──────────────────────────────────────────────────────────────

    @staticmethod
    def criar_sobra(session, inventario_id: int, codigo_lido: str, tipo: TipoSobraEnum,
                    localizacao_id: int, usuario_id: int,
                    descricao_livre: str | None = None) -> InventarioSobra:
        """
        UNIQUE(inventario_id, codigo_lido) torna esta operação idempotente
        por natureza (RN-20 aplicada à sobra, não só ao item): reler o
        mesmo código ilegível/fora de escopo na mesma sessão devolve a
        sobra já registrada, em vez de colidir no índice.
        """
        existente = (session.query(InventarioSobra)
                     .filter(InventarioSobra.inventario_id == inventario_id,
                             InventarioSobra.codigo_lido == codigo_lido)
                     .first())
        if existente:
            return existente

        sobra = InventarioSobra(
            inventario_id=inventario_id,
            codigo_lido=codigo_lido,
            tipo=tipo,
            localizacao_id=localizacao_id,
            descricao_livre=descricao_livre,
            registrado_por=usuario_id,
        )
        session.add(sobra)
        session.flush()
        session.expunge(sobra)
        return sobra

    @staticmethod
    def listar_sobras(inventario_id: int) -> list[InventarioSobra]:
        with get_read_session() as s:
            itens = (s.query(InventarioSobra)
                     .options(joinedload(InventarioSobra.localizacao),
                              joinedload(InventarioSobra.registrado_por_usuario))
                     .filter(InventarioSobra.inventario_id == inventario_id)
                     .order_by(InventarioSobra.registrado_em)
                     .all())
            s.expunge_all()
            return itens

    @staticmethod
    def buscar_sobra(sobra_id: int) -> InventarioSobra | None:
        with get_read_session() as s:
            obj = s.get(InventarioSobra, sobra_id)
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def excluir_sobra(sobra_id: int) -> bool:
        """Única exclusão física do módulo — sobra não é fato patrimonial."""
        with get_session() as s:
            sobra = s.get(InventarioSobra, sobra_id)
            if not sobra:
                return False
            s.delete(sobra)
            return True

    # ─── Tokens ──────────────────────────────────────────────────────────────

    @staticmethod
    def criar_token(session, inventario_id: int, localizacao_conferida_id: int,
                    usuario_id: int, horas_validade: float,
                    dispositivo_label: str | None = None) -> ColetaToken:
        token = ColetaToken(
            token=secrets.token_urlsafe(_TOKEN_BYTES),
            inventario_id=inventario_id,
            localizacao_conferida_id=localizacao_conferida_id,
            usuario_id=usuario_id,
            dispositivo_label=dispositivo_label,
            expira_em=datetime.utcnow() + timedelta(hours=horas_validade),
        )
        session.add(token)
        session.flush()
        session.expunge(token)
        return token

    @staticmethod
    def buscar_token(token: str) -> ColetaToken | None:
        with get_read_session() as s:
            obj = (s.query(ColetaToken)
                   .options(joinedload(ColetaToken.inventario),
                            joinedload(ColetaToken.localizacao_conferida))
                   .filter(ColetaToken.token == token)
                   .first())
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def revogar_tokens_sessao(session, inventario_id: int) -> int:
        return (session.query(ColetaToken)
                .filter(ColetaToken.inventario_id == inventario_id,
                        ColetaToken.revogado == False)  # noqa: E712
                .update({ColetaToken.revogado: True}, synchronize_session=False))
