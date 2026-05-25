"""
MOD-06 · mod06_dados · models.py
Modelos SQLAlchemy mapeando as 9 tabelas do schema sce_db (ERD v2 / DDL v1.1).
"""
import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Integer, String, Enum, Boolean, DateTime, Date,
    Numeric, Time, ForeignKey, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ─── ENUMs Python (espelhando os ENUMs MySQL) ───────────────────────────────

class PerfilEnum(str, enum.Enum):
    tecnico = "tecnico"
    admin = "admin"
    ti      = "ti"


class CentroAlocacaoEnum(str, enum.Enum):
    almoxarifado = "almoxarifado"
    farmacia     = "farmacia"
    deposito     = "deposito"

class UnidadeEstoqueEnum(str, enum.Enum):
    caixa   =   "caixa"
    pacote  =   "pacote"
    unidade =   "unidade"
    fardo   =   "fardo"
    ampola  =   "ampola"
    galao   =   "galao"
    litro   =   "litro"
    rolo    =   "rolo"
    kit     =   "kit"
    dose    =   "dose"


class TipoMovimentacaoEnum(str, enum.Enum):
    entrada_manual = "entrada_manual"
    entrada_nfe    = "entrada_nfe"
    saida          = "saida"
    entrada_danfe  = "entrada_danfe"
    transferencia  = "transferencia"
    baixa_vencido  = "baixa_vencido"

class TipoAlertaEnum(str, enum.Enum):
    vencimento_30  = "vencimento_30"
    vencimento_15   = "vencimento_15"
    vencimento_7   = "vencimento_7"
    vencido        = "vencido"
    estoque_baixo  = "estoque_baixo"


class PeriodicidadeEnum(str, enum.Enum):
    diario  = "diario"
    semanal = "semanal"
    mensal  = "mensal"


class TipoRelatorioEnum(str, enum.Enum):
    movimentacao   = "movimentacao"
    estoque_atual  = "estoque_atual"
    a_vencer       = "a_vencer"
    lotes_vencidos = "lotes_vencidos"


# ─── MODELOS ────────────────────────────────────────────────────────────────

class Usuario(Base):
    """Tabela: usuario — MOD-01"""
    __tablename__ = "usuario"

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome:        Mapped[str]      = mapped_column(String(100), nullable=False)
    login:       Mapped[str]      = mapped_column(String(60),  nullable=False, unique=True)
    senha_hash:  Mapped[str]      = mapped_column(String(255), nullable=False)
    perfil:      Mapped[PerfilEnum] = mapped_column(Enum(PerfilEnum), nullable=False)
    ativo:       Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    criado_em:   Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    movimentacoes: Mapped[list["Movimentacao"]] = relationship(back_populates="usuario")
    configuracoes: Mapped[list["Configuracao"]] = relationship(back_populates="atualizado_por_usuario")

    def __repr__(self):
        return f"<Usuario {self.login} [{self.perfil}]>"




class Produto(Base):
    """Tabela: produto — MOD-02"""
    __tablename__ = "produto"

    id:               Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    fornecedor:       Mapped[str | None]            = mapped_column(String(150), nullable=True)
    nome:             Mapped[str]                   = mapped_column(String(120), nullable=False)
    descricao:        Mapped[str | None]            = mapped_column(String(255), nullable=True)
    ean:              Mapped[str]                   = mapped_column(String(20),  nullable=False, unique=True)
    marca:            Mapped[str | None]            = mapped_column(String(100), nullable=True)
    estoque_minimo:   Mapped[int]                   = mapped_column(Integer, nullable=False, default=0)
    ativo:            Mapped[bool]                  = mapped_column(Boolean, nullable=False, default=True)
    criado_em:        Mapped[datetime]              = mapped_column(DateTime, nullable=False, default=func.now())

    lotes:      Mapped[list["Lote"]]         = relationship(back_populates="produto", order_by="Lote.data_vencimento")

    def __repr__(self):
        return f"<Produto {self.id}: {self.nome} [{self.ean}]>"


class Lote(Base):
    """Tabela: lote — MOD-02"""
    __tablename__ = "lote"

    id:                  Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    produto_id:          Mapped[int]      = mapped_column(Integer, ForeignKey("produto.id"), nullable=False)
    num_lote:            Mapped[str]      = mapped_column(String(60), nullable=False)
    nota_fiscal:         Mapped[str | None]      = mapped_column(String(60), nullable=False)
    chave_acesso:        Mapped[str | None] = mapped_column(String(44), nullable=True)
    data_fabricacao:     Mapped[date | None] = mapped_column(Date, nullable=True)
    data_vencimento:     Mapped[date]     = mapped_column(Date, nullable=False)
    quantidade_inicial:  Mapped[int]      = mapped_column(Integer, nullable=False)
    quantidade_atual:    Mapped[int]      = mapped_column(Integer, nullable=False)
    valor_unitario:      Mapped[Decimal]  = mapped_column(Numeric(10, 2), nullable=False)
    valor_total:         Mapped[Decimal]  = mapped_column(Numeric(10, 2), nullable=False)
    criado_em:           Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    centro_alocacao:  Mapped[CentroAlocacaoEnum]   = mapped_column(Enum(CentroAlocacaoEnum), nullable=False, default=CentroAlocacaoEnum.deposito)
    produto:       Mapped["Produto"]           = relationship(back_populates="lotes")
    movimentacoes: Mapped[list["Movimentacao"]] = relationship(back_populates="lote")
    notificacoes:  Mapped[list["NotificacaoLog"]] = relationship(back_populates="lote")
    unidade_estoque:  Mapped[UnidadeEstoqueEnum]    = mapped_column(Enum(UnidadeEstoqueEnum), nullable=False)
    @property
    def ativo(self) -> bool:
        return self.quantidade_atual > 0

    def __repr__(self):
        return f"<Lote {self.num_lote} | {self.produto_id} | vence {self.data_vencimento} | saldo {self.quantidade_atual}>"


class Movimentacao(Base):
    """Tabela: movimentacao — MOD-02"""
    __tablename__ = "movimentacao"

    id:          Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id:     Mapped[int]                    = mapped_column(Integer, ForeignKey("lote.id"), nullable=False)
    usuario_id:  Mapped[int]                    = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)
    tipo:        Mapped[TipoMovimentacaoEnum]   = mapped_column(Enum(TipoMovimentacaoEnum), nullable=False)
    quantidade:  Mapped[int]                    = mapped_column(Integer, nullable=False)
    numero_nf:   Mapped[str | None]             = mapped_column(String(60), nullable=True)
    observacao:  Mapped[str | None]             = mapped_column(String(255), nullable=True)
    data_hora:   Mapped[datetime]               = mapped_column(DateTime, nullable=False, default=func.now())

    lote:    Mapped["Lote"]    = relationship(back_populates="movimentacoes")
    usuario: Mapped["Usuario"] = relationship(back_populates="movimentacoes")

    def __repr__(self):
        return f"<Movimentacao {self.tipo} | lote {self.lote_id} | qtd {self.quantidade}>"


class NotificacaoLog(Base):
    """Tabela: notificacao_log — MOD-04"""
    __tablename__ = "notificacao_log"

    id:           Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    lote_id:      Mapped[int]            = mapped_column(Integer, ForeignKey("lote.id"), nullable=False)
    tipo_alerta:  Mapped[TipoAlertaEnum] = mapped_column(Enum(TipoAlertaEnum), nullable=False)
    enviado_em:   Mapped[datetime]       = mapped_column(DateTime, nullable=False, default=func.now())
    sucesso:      Mapped[bool]           = mapped_column(Boolean, nullable=False)
    erro_msg:     Mapped[str | None]     = mapped_column(String(255), nullable=True)

    lote: Mapped["Lote"] = relationship(back_populates="notificacoes")


class JobLog(Base):
    """Tabela: job_log — MOD-04"""
    __tablename__ = "job_log"

    id:           Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_nome:     Mapped[str]        = mapped_column(String(60),  nullable=False)
    executado_em: Mapped[datetime]   = mapped_column(DateTime, nullable=False, default=func.now())
    sucesso:      Mapped[bool]       = mapped_column(Boolean, nullable=False)
    detalhe:      Mapped[str | None] = mapped_column(String(255), nullable=True)


class Configuracao(Base):
    """Tabela: configuracao — MOD-05"""
    __tablename__ = "configuracao"

    id:             Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave:          Mapped[str]      = mapped_column(String(120), nullable=False, unique=True)
    valor:          Mapped[str]      = mapped_column(String(500), nullable=False)
    atualizado_em:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    atualizado_por: Mapped[int]      = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)

    atualizado_por_usuario: Mapped["Usuario"] = relationship(back_populates="configuracoes")


class RelatorioAgendamento(Base):
    """Tabela: relatorio_agendamento — MOD-03"""
    __tablename__ = "relatorio_agendamento"

    id:             Mapped[int]                 = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo_relatorio: Mapped[TipoRelatorioEnum]   = mapped_column(Enum(TipoRelatorioEnum), nullable=False, unique=True)
    habilitado:     Mapped[bool]                = mapped_column(Boolean, nullable=False, default=False)
    periodicidade:  Mapped[PeriodicidadeEnum]   = mapped_column(Enum(PeriodicidadeEnum), nullable=False)
    horario:        Mapped[str]                 = mapped_column(Time, nullable=False)
    ultimo_envio:   Mapped[datetime | None]     = mapped_column(DateTime, nullable=True)
