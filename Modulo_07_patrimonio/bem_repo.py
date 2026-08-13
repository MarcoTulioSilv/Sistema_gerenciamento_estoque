"""
MOD-07 · Modulo_07_patrimonio · bem_repo.py
Repositório de bens patrimoniais e movimentações — acesso via MOD-06.
"""
import logging
from datetime import date, datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from Modulo_06_dados import (
    get_session, get_read_session,
    BemPatrimonial, Localizacao, MovimentacaoBem, BaixaBem,
    SituacaoBemEnum, TipoMovimentacaoBemEnum, MotivoBaixaEnum,
)
from .dto import FiltroBens, DadosBem

logger = logging.getLogger(__name__)


class BemRepo:

    @staticmethod
    def listar(filtro: FiltroBens | None = None) -> list[BemPatrimonial]:
        filtro = filtro or FiltroBens()
        with get_read_session() as s:
            q = s.query(BemPatrimonial).options(joinedload(BemPatrimonial.localizacao))

            if filtro.texto:
                alvo = f"%{filtro.texto.strip()}%"
                q = q.filter(or_(
                    BemPatrimonial.tombo.ilike(alvo),
                    BemPatrimonial.descricao.ilike(alvo),
                ))
            if filtro.localizacao_id is not None:
                q = q.filter(BemPatrimonial.localizacao_id == filtro.localizacao_id)
            if filtro.situacao:
                q = q.filter(BemPatrimonial.situacao == SituacaoBemEnum(filtro.situacao))
            elif filtro.apenas_ativos:
                q = q.filter(BemPatrimonial.situacao == SituacaoBemEnum.ativo)

            if filtro.ordenar_por == "localizacao":
                q = q.join(Localizacao).order_by(Localizacao.setor, Localizacao.sala)
            elif filtro.ordenar_por == "descricao":
                q = q.order_by(BemPatrimonial.descricao)
            else:
                q = q.order_by(BemPatrimonial.tombo)

            if filtro.limite:
                q = q.limit(filtro.limite)

            itens = q.all()
            s.expunge_all()
            return itens

    @staticmethod
    def buscar_por_id(id_: int) -> BemPatrimonial | None:
        with get_read_session() as s:
            obj = (s.query(BemPatrimonial)
                   .options(joinedload(BemPatrimonial.localizacao))
                   .filter(BemPatrimonial.id == id_)
                   .first())
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def buscar_por_tombo(tombo: str) -> BemPatrimonial | None:
        # Trim + case-insensitive: o tombo pode chegar de leitor de código de
        # barras ou digitação manual, com espaços/caixa inconsistentes.
        alvo = tombo.strip().lower()
        with get_read_session() as s:
            obj = (s.query(BemPatrimonial)
                   .options(joinedload(BemPatrimonial.localizacao))
                   .filter(func.lower(func.trim(BemPatrimonial.tombo)) == alvo)
                   .first())
            if obj:
                s.expunge(obj)
            return obj

    @staticmethod
    def criar(session, tombo: str, dados: DadosBem, usuario_id: int) -> BemPatrimonial:
        """
        Cria o bem e registra a movimentação de cadastro na MESMA sessão já
        aberta pelo chamador — participa da transação do TomboGenerator
        (SELECT ... FOR UPDATE em configuracao), não abre a própria.
        """
        bem = BemPatrimonial(
            tombo=tombo,
            descricao=dados.descricao,
            marca_modelo=dados.marca_modelo,
            data_aquisicao=dados.data_aquisicao,
            valor_aquisicao=dados.valor_aquisicao,
            nota_fiscal=dados.nota_fiscal,
            localizacao_id=dados.localizacao_id,
            observacao=dados.observacao,
            criado_por=usuario_id,
        )
        session.add(bem)
        session.flush()  # gera bem.id

        mov = MovimentacaoBem(
            bem_id=bem.id,
            tipo=TipoMovimentacaoBemEnum.cadastro,
            localizacao_destino_id=dados.localizacao_id,
            usuario_id=usuario_id,
            data_hora=datetime.utcnow(),
        )
        session.add(mov)
        session.flush()
        _ = bem.localizacao  # carrega o relacionamento antes de desanexar
        session.expunge(bem)
        return bem

    @staticmethod
    def atualizar(bem_id: int, dados: DadosBem) -> BemPatrimonial | None:
        # Só campos descritivos — localizacao_id nunca muda aqui (é transferir()).
        with get_session() as s:
            bem = s.get(BemPatrimonial, bem_id)
            if not bem:
                return None
            bem.descricao = dados.descricao
            bem.marca_modelo = dados.marca_modelo
            bem.data_aquisicao = dados.data_aquisicao
            bem.valor_aquisicao = dados.valor_aquisicao
            bem.nota_fiscal = dados.nota_fiscal
            bem.observacao = dados.observacao
            s.flush()
            _ = bem.localizacao
            s.expunge(bem)
            return bem

    @staticmethod
    def transferir(bem_id: int, localizacao_destino_id: int, motivo: str, usuario_id: int) -> BemPatrimonial | None:
        with get_session() as s:
            bem = s.get(BemPatrimonial, bem_id)
            if not bem:
                return None
            origem_id = bem.localizacao_id
            bem.localizacao_id = localizacao_destino_id

            mov = MovimentacaoBem(
                bem_id=bem.id,
                tipo=TipoMovimentacaoBemEnum.transferencia,
                localizacao_origem_id=origem_id,
                localizacao_destino_id=localizacao_destino_id,
                motivo=motivo,
                usuario_id=usuario_id,
                data_hora=datetime.utcnow(),
            )
            s.add(mov)
            s.flush()
            s.expire(bem, ["localizacao"])  # recarrega para refletir o novo destino
            _ = bem.localizacao
            s.expunge(bem)
            return bem

    @staticmethod
    def baixar(
        bem_id: int,
        motivo: MotivoBaixaEnum,
        data_baixa: date,
        usuario_id: int,
        documento: str | None = None,
        observacao: str | None = None,
    ) -> BemPatrimonial | None:
        with get_session() as s:
            bem = s.get(BemPatrimonial, bem_id)
            if not bem:
                return None

            baixa = BaixaBem(
                bem_id=bem.id,
                motivo=motivo,
                documento=documento,
                data_baixa=data_baixa,
                observacao=observacao,
                usuario_id=usuario_id,
                registrado_em=datetime.utcnow(),
            )
            s.add(baixa)

            bem.situacao = SituacaoBemEnum.baixado

            mov = MovimentacaoBem(
                bem_id=bem.id,
                tipo=TipoMovimentacaoBemEnum.baixa,
                motivo=motivo.value,
                usuario_id=usuario_id,
                data_hora=datetime.utcnow(),
            )
            s.add(mov)
            s.flush()
            _ = bem.localizacao
            s.expunge(bem)
            return bem

    @staticmethod
    def historico(bem_id: int) -> list[MovimentacaoBem]:
        with get_read_session() as s:
            itens = (s.query(MovimentacaoBem)
                     .options(
                         joinedload(MovimentacaoBem.localizacao_origem),
                         joinedload(MovimentacaoBem.localizacao_destino),
                         joinedload(MovimentacaoBem.usuario),
                     )
                     .filter(MovimentacaoBem.bem_id == bem_id)
                     .order_by(MovimentacaoBem.data_hora)
                     .all())
            s.expunge_all()
            return itens
