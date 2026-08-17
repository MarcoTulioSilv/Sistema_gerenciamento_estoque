"""
MOD-06 · mod06_dados · models.py
Modelos SQLAlchemy do schema sce_db.
MOD-01 a MOD-06: DDL v1.4 (reverse-engineered da producao).
MOD-07 Patrimonio: migracoes 007_patrimonio.sql e 008_patrimonio_v2.sql
(ERS v1.8 / DAS v1.5).
"""
import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Integer, String, Enum, Boolean, DateTime, Date,
    Numeric, Time, ForeignKey, Text, func, Index, Computed, CHAR
)
from sqlalchemy.dialects.mysql import MEDIUMBLOB
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
    # MOD-07 · RF-39 / RN-21 — permissao ORTOGONAL ao perfil (AD-23).
    # Primeira permissao do SCE que nao deriva de `perfil`. DEFAULT False faz
    # a migracao falhar para o lado seguro: apos aplica-la, somente o perfil
    # `ti` acessa o subsistema, ate que a permissao seja concedida.
    acesso_patrimonio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em:   Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    movimentacoes: Mapped[list["Movimentacao"]] = relationship(back_populates="usuario")
    configuracoes: Mapped[list["Configuracao"]] = relationship(back_populates="atualizado_por_usuario")

    @property
    def pode_acessar_patrimonio(self) -> bool:
        """
        RN-21 — o perfil TI acessa por definicao; os demais dependem da
        permissao explicita, concedida somente pelo TI (RN-22).

        Conveniencia de leitura. NAO substitui a verificacao no service: a
        entidade pode estar desanexada e desatualizada em relacao ao banco.
        """
        return self.perfil == PerfilEnum.ti or self.acesso_patrimonio

    def __repr__(self):
        return f"<Usuario {self.login} [{self.perfil}]>"




class Produto(Base):
    """Tabela: produto — MOD-02"""
    __tablename__ = "produto"

    id:               Mapped[int]                   = mapped_column(Integer, primary_key=True, autoincrement=True)
    fornecedor:       Mapped[str | None]            = mapped_column(String(150), nullable=True)
    nome:             Mapped[str]                   = mapped_column(String(120), nullable=False)
    descricao:        Mapped[str | None]            = mapped_column(String(255), nullable=True)
    ean:              Mapped[str]                   = mapped_column(String(20),  nullable=False, unique=True)
    marca:            Mapped[str | None]            = mapped_column(String(100), nullable=True)
    estoque_minimo:   Mapped[int]                   = mapped_column(Integer, nullable=False, default=0)
    ativo:            Mapped[bool]                  = mapped_column(Boolean, nullable=False, default=True)
    criado_em:        Mapped[datetime]              = mapped_column(DateTime, nullable=False, default=func.now())
    lotes:            Mapped[list["Lote"]]          = relationship(back_populates="produto", order_by="Lote.data_vencimento")
    controla_validade: Mapped[bool]                 = mapped_column(Boolean, default= True, nullable=False)

    def __repr__(self):
        return f"<Produto {self.id}: {self.nome} [{self.ean}]>"


class Lote(Base):
    """Tabela: lote — MOD-02"""
    __tablename__ = "lote"

    id:                  Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    produto_id:          Mapped[int]                    = mapped_column(Integer, ForeignKey("produto.id"), nullable=False)
    num_lote:            Mapped[str]                    = mapped_column(String(60), nullable=True)
    nota_fiscal:         Mapped[str | None]             = mapped_column(String(60), nullable=False)
    chave_acesso:        Mapped[str | None]             = mapped_column(String(44), nullable=True)
    data_fabricacao:     Mapped[date | None]            = mapped_column(Date, nullable=True)
    data_vencimento:     Mapped[date]                   = mapped_column(Date, nullable=True)
    quantidade_inicial:  Mapped[int]                    = mapped_column(Integer, nullable=False)
    quantidade_atual:    Mapped[int]                    = mapped_column(Integer, nullable=False)
    valor_unitario:      Mapped[Decimal]                = mapped_column(Numeric(10, 2), nullable=False)
    valor_total:         Mapped[Decimal]                = mapped_column(Numeric(10, 2), nullable=False)
    criado_em:           Mapped[datetime]               = mapped_column(DateTime, nullable=False, default=func.now())
    centro_alocacao:     Mapped[CentroAlocacaoEnum]     = mapped_column(Enum(CentroAlocacaoEnum), nullable=False, default=CentroAlocacaoEnum.deposito)
    produto:             Mapped["Produto"]              = relationship(back_populates="lotes")
    movimentacoes:       Mapped[list["Movimentacao"]]   = relationship(back_populates="lote")
    notificacoes:        Mapped[list["NotificacaoLog"]] = relationship(back_populates="lote")
    unidade_estoque:     Mapped[UnidadeEstoqueEnum]     = mapped_column(Enum(UnidadeEstoqueEnum), nullable=False)

    __table_args__ = (
        Index('idx_saida_estoque', 'produto_id', 'data_vencimento', 'criado_em'),
        # Cobre buscas cross-produto por vencimento sem produto_id no WHERE
        # (ex.: NotificacaoService.verificar_vencimentos/alertar_lotes_vencidos).
        Index('idx_lote_vencimento', 'data_vencimento'),
    )

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
    quantidade:  Mapped[int]                    = mapped_column(Integer, nullable=True)
    numero_nf:   Mapped[str | None]             = mapped_column(String(60), nullable=True)
    observacao:  Mapped[str | None]             = mapped_column(String(255), nullable=True)
    data_hora:   Mapped[datetime]               = mapped_column(DateTime, nullable=False, default=func.now())

    lote:    Mapped["Lote"]    = relationship(back_populates="movimentacoes")
    usuario: Mapped["Usuario"] = relationship(back_populates="movimentacoes")

    __table_args__ = (
        Index('idx_mov_lote_hora', 'lote_id', 'data_hora'),
        Index('idx_mov_usuario', 'usuario_id'),
        # Cobre buscas por período sem lote_id no WHERE (ex.: KPI "movimentações
        # hoje" da T-02 e o filtro de datas da T-19).
        Index('idx_mov_data_hora', 'data_hora'),
    )

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

    __table_args__ = (
        Index('idx_notif_lote_tipo_data', 'lote_id', 'tipo_alerta', 'enviado_em'),
    )


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


class GrupoConsumo(Base):
    """
    Tabela: grupo_consumo — MOD-03
    Agrupa produtos "irmãos" (mesmo item, marcas/nomes diferentes) para o
    relatório de consumo médio, via palavras-chave (todas precisam bater no
    nome do produto, AND — não OR). Mantido pela tela de gestão em T-11.
    """
    __tablename__ = "grupo_consumo"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome:         Mapped[str]      = mapped_column(String(120), nullable=False, unique=True)
    termos_chave: Mapped[str]      = mapped_column(String(255), nullable=False)
    criado_em:    Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())


class VwSaldoProduto(Base):
    """view de saldo total de produtos"""
    __tablename__ = "vw_saldo_produtos"

    id:             Mapped[int]        = mapped_column("produto_id", Integer, primary_key=True)
    nome:           Mapped[str]        = mapped_column(String(120))
    ean:            Mapped[str]        = mapped_column(String(20))
    marca:          Mapped[str | None] = mapped_column(String(100), nullable=True)
    fornecedor:     Mapped[str | None] = mapped_column(String(150), nullable=True)
    estoque_minimo: Mapped[int]        = mapped_column(Integer)
    ativo:          Mapped[bool]       = mapped_column(Boolean)
    saldo_total:    Mapped[Decimal]    = mapped_column(Numeric(10, 2))


# ════════════════════════════════════════════════════════════════════════════
# MOD-07 · PATRIMÔNIO
# Tabelas criadas pela migração 007_patrimonio.sql (ERS v1.7 / DAS v1.4).
# MOD-07 não referencia produto nem lote: a separação de domínios é
# deliberada (AD-13) e está explícita tanto no schema quanto aqui.
# ════════════════════════════════════════════════════════════════════════════


# ─── ENUMs do MOD-07 ────────────────────────────────────────────────────────

class SituacaoBemEnum(str, enum.Enum):
    ativo       = "ativo"
    em_apuracao = "em_apuracao"   # não localizado em sessão fechada (RN-15)
    baixado     = "baixado"       # baixa registrada (RN-12)


class TipoMovimentacaoBemEnum(str, enum.Enum):
    cadastro          = "cadastro"
    transferencia     = "transferencia"
    ajuste_inventario = "ajuste_inventario"   # sempre vinculado a inventario_id
    baixa             = "baixa"


class MotivoBaixaEnum(str, enum.Enum):
    descarte      = "descarte"
    doacao        = "doacao"
    venda         = "venda"
    extravio      = "extravio"
    obsolescencia = "obsolescencia"
    sinistro      = "sinistro"


class EscopoInventarioEnum(str, enum.Enum):
    geral       = "geral"
    localizacao = "localizacao"


class StatusInventarioEnum(str, enum.Enum):
    aberto     = "aberto"
    finalizado = "finalizado"
    cancelado  = "cancelado"


class StatusItemInventarioEnum(str, enum.Enum):
    pendente         = "pendente"
    encontrado       = "encontrado"
    divergente_local = "divergente_local"
    nao_localizado   = "nao_localizado"


class TipoSobraEnum(str, enum.Enum):
    fora_escopo    = "fora_escopo"      # tombo existe, fora do escopo da sessão
    nao_cadastrado = "nao_cadastrado"   # código lido não corresponde a tombo


# ─── MODELOS DO MOD-07 ──────────────────────────────────────────────────────

class Localizacao(Base):
    """Tabela: localizacao — MOD-07"""
    __tablename__ = "localizacao"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    setor:      Mapped[str]        = mapped_column(String(80),  nullable=False)
    sala:       Mapped[str]        = mapped_column(String(80),  nullable=False)
    descricao:  Mapped[str | None] = mapped_column(String(255), nullable=True)
    ativo:      Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True)
    criado_em:  Mapped[datetime]   = mapped_column(DateTime, nullable=False, default=func.now())

    bens: Mapped[list["BemPatrimonial"]] = relationship(back_populates="localizacao")

    __table_args__ = (
        Index('uq_localizacao_setor_sala', 'setor', 'sala', unique=True),
        Index('idx_localizacao_ativo', 'ativo'),
    )

    @property
    def nome_completo(self) -> str:
        """Rótulo de exibição usado nas telas e no relatório."""
        return f"{self.setor} — {self.sala}"

    def __repr__(self):
        return f"<Localizacao {self.id}: {self.setor} / {self.sala}>"


class BemPatrimonial(Base):
    """
    Tabela: bem_patrimonial — MOD-07

    Bem permanente identificado unitariamente pelo tombo (RN-09: único e
    imutável após a emissão). Campos de aquisição são todos opcionais por
    decisão de escopo — não há depreciação nem valor contábil nesta versão.
    """
    __tablename__ = "bem_patrimonial"

    id:               Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    tombo:            Mapped[str]              = mapped_column(String(30),  nullable=False)
    descricao:        Mapped[str]              = mapped_column(String(160), nullable=False)
    marca_modelo:     Mapped[str | None]       = mapped_column(String(120), nullable=True)
    data_aquisicao:   Mapped[date | None]      = mapped_column(Date, nullable=True)
    valor_aquisicao:  Mapped[Decimal | None]   = mapped_column(Numeric(10, 2), nullable=True)
    nota_fiscal:      Mapped[str | None]       = mapped_column(String(60),  nullable=True)
    localizacao_id:   Mapped[int]              = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=False)
    situacao:         Mapped[SituacaoBemEnum]  = mapped_column(Enum(SituacaoBemEnum), nullable=False, default=SituacaoBemEnum.ativo)
    observacao:       Mapped[str | None]       = mapped_column(String(500), nullable=True)
    criado_em:        Mapped[datetime]         = mapped_column(DateTime, nullable=False, default=func.now())
    criado_por:       Mapped[int]              = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)

    localizacao:   Mapped["Localizacao"]            = relationship(back_populates="bens")
    movimentacoes: Mapped[list["MovimentacaoBem"]]  = relationship(back_populates="bem", order_by="MovimentacaoBem.data_hora")
    baixa:         Mapped["BaixaBem | None"]        = relationship(back_populates="bem", uselist=False)
    itens_inventario: Mapped[list["InventarioItem"]] = relationship(back_populates="bem")
    manutencoes:   Mapped[list["ManutencaoBem"]]    = relationship(
        back_populates="bem", order_by="ManutencaoBem.data_manutencao")

    __table_args__ = (
        Index('uq_bem_tombo', 'tombo', unique=True),
        Index('idx_bem_localizacao_situacao', 'localizacao_id', 'situacao'),
        Index('idx_bem_descricao', 'descricao'),
        Index('idx_bem_criado_por', 'criado_por'),
    )

    @property
    def ativo(self) -> bool:
        """Bem em uso — entra no snapshot de novas sessões de inventário."""
        return self.situacao == SituacaoBemEnum.ativo

    def __repr__(self):
        return f"<BemPatrimonial {self.tombo}: {self.descricao} [{self.situacao}]>"


class Inventario(Base):
    """
    Tabela: inventario — MOD-07

    Sessão de conferência física. A coluna escopo_aberto é GERADA pelo banco
    e implementa parte da RN-16: enquanto a sessão está aberta ela guarda o
    id da localização (ou 0 para escopo geral); ao finalizar, vira NULL — e
    índice único ignora NULL, liberando a área para uma sessão futura.

    LIMITE: a regra "sessão geral bloqueia qualquer outra" não é expressável
    por índice único e permanece sob responsabilidade de
    InventarioService.abrir_sessao().
    """
    __tablename__ = "inventario"

    id:              Mapped[int]                   = mapped_column(Integer, primary_key=True, autoincrement=True)
    descricao:       Mapped[str]                   = mapped_column(String(160), nullable=False)
    escopo:          Mapped[EscopoInventarioEnum]  = mapped_column(Enum(EscopoInventarioEnum), nullable=False)
    localizacao_id:  Mapped[int | None]            = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=True)
    status:          Mapped[StatusInventarioEnum]  = mapped_column(Enum(StatusInventarioEnum), nullable=False, default=StatusInventarioEnum.aberto)
    aberto_em:       Mapped[datetime]              = mapped_column(DateTime, nullable=False, default=func.now())
    aberto_por:      Mapped[int]                   = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)
    finalizado_em:   Mapped[datetime | None]       = mapped_column(DateTime, nullable=True)
    finalizado_por:  Mapped[int | None]            = mapped_column(Integer, ForeignKey("usuario.id"), nullable=True)

    # Coluna gerada pelo banco — nunca escrita pela aplicação.
    escopo_aberto:   Mapped[int | None]            = mapped_column(
        Integer,
        Computed("(CASE WHEN `status` = 'aberto' THEN COALESCE(`localizacao_id`, 0) ELSE NULL END)", persisted=True),
        nullable=True,
    )

    localizacao: Mapped["Localizacao | None"]        = relationship(foreign_keys=[localizacao_id])
    itens:       Mapped[list["InventarioItem"]]      = relationship(back_populates="inventario")
    sobras:      Mapped[list["InventarioSobra"]]     = relationship(back_populates="inventario")
    tokens:      Mapped[list["ColetaToken"]]         = relationship(back_populates="inventario")
    aberto_por_usuario:     Mapped["Usuario"]        = relationship(foreign_keys=[aberto_por])
    finalizado_por_usuario: Mapped["Usuario | None"] = relationship(foreign_keys=[finalizado_por])

    __table_args__ = (
        Index('uq_inventario_escopo_aberto', 'escopo_aberto', unique=True),
        Index('idx_inventario_status', 'status'),
        Index('idx_inventario_localizacao', 'localizacao_id'),
        Index('idx_inventario_aberto_por', 'aberto_por'),
        Index('idx_inventario_finalizado_por', 'finalizado_por'),
    )

    @property
    def aberta(self) -> bool:
        return self.status == StatusInventarioEnum.aberto

    def __repr__(self):
        return f"<Inventario {self.id}: {self.descricao} [{self.escopo}/{self.status}]>"


class MovimentacaoBem(Base):
    """
    Tabela: movimentacao_bem — MOD-07

    Histórico do bem. SOMENTE INCREMENTAL (RN-11): correção se faz por nova
    linha, nunca por UPDATE ou DELETE. inventario_id só é preenchido em
    ajuste_inventario, vinculando o ajuste à sessão que o originou (RN-14).
    """
    __tablename__ = "movimentacao_bem"

    id:                      Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    bem_id:                  Mapped[int]                      = mapped_column(Integer, ForeignKey("bem_patrimonial.id"), nullable=False)
    tipo:                    Mapped[TipoMovimentacaoBemEnum]  = mapped_column(Enum(TipoMovimentacaoBemEnum), nullable=False)
    localizacao_origem_id:   Mapped[int | None]               = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=True)
    localizacao_destino_id:  Mapped[int | None]               = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=True)
    inventario_id:           Mapped[int | None]               = mapped_column(Integer, ForeignKey("inventario.id"), nullable=True)
    motivo:                  Mapped[str | None]               = mapped_column(String(255), nullable=True)
    usuario_id:              Mapped[int]                      = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)
    data_hora:               Mapped[datetime]                 = mapped_column(DateTime, nullable=False, default=func.now())

    bem:                 Mapped["BemPatrimonial"]     = relationship(back_populates="movimentacoes")
    localizacao_origem:  Mapped["Localizacao | None"] = relationship(foreign_keys=[localizacao_origem_id])
    localizacao_destino: Mapped["Localizacao | None"] = relationship(foreign_keys=[localizacao_destino_id])
    inventario:          Mapped["Inventario | None"]  = relationship(foreign_keys=[inventario_id])
    usuario:             Mapped["Usuario"]            = relationship(foreign_keys=[usuario_id])

    __table_args__ = (
        Index('idx_mov_bem_hora', 'bem_id', 'data_hora'),
        Index('idx_mov_bem_tipo', 'tipo'),
        Index('idx_mov_bem_usuario', 'usuario_id'),
        Index('idx_mov_bem_origem', 'localizacao_origem_id'),
        Index('idx_mov_bem_destino', 'localizacao_destino_id'),
        Index('idx_mov_bem_inventario', 'inventario_id'),
    )

    def __repr__(self):
        return f"<MovimentacaoBem {self.tipo} | bem {self.bem_id} | {self.data_hora}>"


class BaixaBem(Base):
    """
    Tabela: baixa_bem — MOD-07

    Baixa lógica e irreversível pela interface (RN-12). O UNIQUE em bem_id é
    o que impede baixa dupla — a garantia está no banco, não na camada de
    serviço.

    ANEXO OBRIGATORIO (RF-30, v1.8): `documento_id` e NOT NULL. A chave
    estrangeira parte DAQUI para `baixa_documento`, e nao o contrario — e
    essa direcao que torna a obrigatoriedade verificavel pelo banco em
    qualquer caminho de escrita (AD-22). Com o vinculo no sentido inverso, o
    NOT NULL garantiria apenas que um documento existente aponte para uma
    baixa, nunca que toda baixa tenha documento.

    Ordem de gravacao na transacao: insere `baixa_documento`, obtem o id,
    insere `baixa_bem`. Falha em qualquer ponto desfaz os dois.

    A coluna `documento` (texto livre) permanece como referencia a ata,
    termo ou processo — nao e substituta do anexo nem dos numeros de MTR e
    laudo.
    """
    __tablename__ = "baixa_bem"

    id:             Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    bem_id:         Mapped[int]              = mapped_column(Integer, ForeignKey("bem_patrimonial.id"), nullable=False)
    motivo:         Mapped[MotivoBaixaEnum]  = mapped_column(Enum(MotivoBaixaEnum), nullable=False)
    documento:      Mapped[str | None]       = mapped_column(String(120), nullable=True)
    numero_mtr:     Mapped[str | None]       = mapped_column(String(60),  nullable=True)
    numero_laudo:   Mapped[str | None]       = mapped_column(String(60),  nullable=True)
    documento_id:   Mapped[int]              = mapped_column(Integer, ForeignKey("baixa_documento.id"), nullable=False)
    data_baixa:     Mapped[date]             = mapped_column(Date, nullable=False)
    observacao:     Mapped[str | None]       = mapped_column(String(500), nullable=True)
    usuario_id:     Mapped[int]              = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)
    registrado_em:  Mapped[datetime]         = mapped_column(DateTime, nullable=False, default=func.now())

    bem:       Mapped["BemPatrimonial"] = relationship(back_populates="baixa")
    usuario:   Mapped["Usuario"]        = relationship(foreign_keys=[usuario_id])
    # lazy="raise" impede carga acidental do BLOB: qualquer acesso a este
    # relacionamento sem carga explicita levanta erro em vez de trazer
    # megabytes em silencio. Use joinedload/selectinload ao abrir o anexo.
    documento_pdf: Mapped["BaixaDocumento"] = relationship(
        foreign_keys=[documento_id], lazy="raise")

    __table_args__ = (
        Index('uq_baixa_bem', 'bem_id', unique=True),
        Index('uq_baixa_documento_id', 'documento_id', unique=True),
        Index('idx_baixa_data', 'data_baixa'),
        Index('idx_baixa_usuario', 'usuario_id'),
    )

    def __repr__(self):
        return f"<BaixaBem bem {self.bem_id} | {self.motivo} | {self.data_baixa}>"


class InventarioItem(Base):
    """
    Tabela: inventario_item — MOD-07

    Snapshot materializado na abertura da sessão (AD-19 / RN-13). O UNIQUE
    (inventario_id, bem_id) é o mecanismo de idempotência da RN-20: leituras
    simultâneas de dois dispositivos colidem no índice, não em verificação de
    memória.

    localizacao_esperada_id é COPIADA na abertura, não derivada do bem: se o
    bem for movimentado durante a sessão, o snapshot precisa preservar onde
    ele deveria estar quando a sessão começou.
    """
    __tablename__ = "inventario_item"

    id:                          Mapped[int]                        = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventario_id:               Mapped[int]                        = mapped_column(Integer, ForeignKey("inventario.id"), nullable=False)
    bem_id:                      Mapped[int]                        = mapped_column(Integer, ForeignKey("bem_patrimonial.id"), nullable=False)
    localizacao_esperada_id:     Mapped[int]                        = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=False)
    status:                      Mapped[StatusItemInventarioEnum]   = mapped_column(Enum(StatusItemInventarioEnum), nullable=False, default=StatusItemInventarioEnum.pendente)
    localizacao_encontrada_id:   Mapped[int | None]                 = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=True)
    conferido_em:                Mapped[datetime | None]            = mapped_column(DateTime, nullable=True)
    conferido_por:               Mapped[int | None]                 = mapped_column(Integer, ForeignKey("usuario.id"), nullable=True)
    observacao:                  Mapped[str | None]                 = mapped_column(String(255), nullable=True)

    inventario:             Mapped["Inventario"]         = relationship(back_populates="itens")
    bem:                    Mapped["BemPatrimonial"]     = relationship(back_populates="itens_inventario")
    localizacao_esperada:   Mapped["Localizacao"]        = relationship(foreign_keys=[localizacao_esperada_id])
    localizacao_encontrada: Mapped["Localizacao | None"] = relationship(foreign_keys=[localizacao_encontrada_id])
    conferido_por_usuario:  Mapped["Usuario | None"]     = relationship(foreign_keys=[conferido_por])

    __table_args__ = (
        Index('uq_inv_item_sessao_bem', 'inventario_id', 'bem_id', unique=True),
        Index('idx_inv_item_sessao_status', 'inventario_id', 'status'),
        Index('idx_inv_item_bem', 'bem_id'),
        Index('idx_inv_item_loc_esperada', 'localizacao_esperada_id'),
        Index('idx_inv_item_loc_encontrada', 'localizacao_encontrada_id'),
        Index('idx_inv_item_conferido_por', 'conferido_por'),
    )

    @property
    def divergente(self) -> bool:
        return self.status == StatusItemInventarioEnum.divergente_local

    def __repr__(self):
        return f"<InventarioItem sessao {self.inventario_id} | bem {self.bem_id} | {self.status}>"


class InventarioSobra(Base):
    """
    Tabela: inventario_sobra — MOD-07

    Leituras que não correspondem a item do snapshot. Tabela SEPARADA de
    inventario_item porque a sobra pode não ter bem_id algum — o código lido
    pode não existir no cadastro. codigo_lido guarda o texto bruto, única
    evidência do que foi encontrado em campo.
    """
    __tablename__ = "inventario_sobra"

    id:               Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventario_id:    Mapped[int]            = mapped_column(Integer, ForeignKey("inventario.id"), nullable=False)
    codigo_lido:      Mapped[str]            = mapped_column(String(120), nullable=False)
    tipo:             Mapped[TipoSobraEnum]  = mapped_column(Enum(TipoSobraEnum), nullable=False)
    localizacao_id:   Mapped[int]            = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=False)
    descricao_livre:  Mapped[str | None]     = mapped_column(String(255), nullable=True)
    registrado_em:    Mapped[datetime]       = mapped_column(DateTime, nullable=False, default=func.now())
    registrado_por:   Mapped[int]            = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)

    inventario:            Mapped["Inventario"]  = relationship(back_populates="sobras")
    localizacao:           Mapped["Localizacao"] = relationship(foreign_keys=[localizacao_id])
    registrado_por_usuario: Mapped["Usuario"]    = relationship(foreign_keys=[registrado_por])

    __table_args__ = (
        Index('uq_inv_sobra_sessao_codigo', 'inventario_id', 'codigo_lido', unique=True),
        Index('idx_inv_sobra_sessao_tipo', 'inventario_id', 'tipo'),
        Index('idx_inv_sobra_localizacao', 'localizacao_id'),
        Index('idx_inv_sobra_registrado_por', 'registrado_por'),
    )

    def __repr__(self):
        return f"<InventarioSobra sessao {self.inventario_id} | {self.codigo_lido} | {self.tipo}>"


class ColetaToken(Base):
    """
    Tabela: coleta_token — MOD-07

    Pareamento de dispositivo móvel à sessão (AD-16 / RN-19). Uma linha por
    aparelho: vários celulares podem estar pareados ao mesmo tempo, cada um
    com sua localização e seu operador, preservando a rastreabilidade em
    inventario_item.conferido_por.

    Revogação é lógica, não exclusão: o histórico de qual dispositivo
    registrou o quê precisa sobreviver ao fechamento da sessão.
    """
    __tablename__ = "coleta_token"

    id:                         Mapped[int]         = mapped_column(Integer, primary_key=True, autoincrement=True)
    token:                      Mapped[str]         = mapped_column(CHAR(43), nullable=False)
    inventario_id:              Mapped[int]         = mapped_column(Integer, ForeignKey("inventario.id"), nullable=False)
    localizacao_conferida_id:   Mapped[int]         = mapped_column(Integer, ForeignKey("localizacao.id"), nullable=False)
    usuario_id:                 Mapped[int]         = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)
    dispositivo_label:          Mapped[str | None]  = mapped_column(String(60), nullable=True)
    criado_em:                  Mapped[datetime]    = mapped_column(DateTime, nullable=False, default=func.now())
    expira_em:                  Mapped[datetime]    = mapped_column(DateTime, nullable=False)
    revogado:                   Mapped[bool]        = mapped_column(Boolean, nullable=False, default=False)

    inventario:            Mapped["Inventario"]  = relationship(back_populates="tokens")
    localizacao_conferida: Mapped["Localizacao"] = relationship(foreign_keys=[localizacao_conferida_id])
    usuario:               Mapped["Usuario"]     = relationship(foreign_keys=[usuario_id])

    __table_args__ = (
        Index('uq_coleta_token', 'token', unique=True),
        Index('idx_coleta_token_sessao', 'inventario_id', 'revogado'),
        Index('idx_coleta_token_localizacao', 'localizacao_conferida_id'),
        Index('idx_coleta_token_usuario', 'usuario_id'),
    )

    @property
    def valido(self) -> bool:
        """
        Validade local do token. NÃO substitui a checagem no serviço, que
        também confirma se a sessão continua aberta.
        """
        return (not self.revogado) and self.expira_em > datetime.now()

    def __repr__(self):
        return f"<ColetaToken sessao {self.inventario_id} | {self.dispositivo_label} | revogado={self.revogado}>"


class BaixaDocumento(Base):
    """
    Tabela: baixa_documento — MOD-07 (v1.8)

    Anexo PDF da baixa, armazenado como BLOB no banco (AD-22).

    TABELA SEPARADA de `baixa_bem` por decisao de desempenho: com o BLOB na
    mesma tabela, toda consulta a baixas arrastaria os PDFs junto — o
    relatorio de bens baixados no ano traria dezenas de megabytes para a
    memoria do cliente sem necessidade. Aqui `baixa_bem` permanece leve e o
    conteudo e buscado apenas quando o usuario abre o documento.

    NAO ha coluna `baixa_id`: o vinculo e declarado em
    `baixa_bem.documento_id`, e essa direcao e o que permite o NOT NULL.

    `conteudo` usa MEDIUMBLOB (16 MB) e nao BLOB (64 KB) — um PDF
    digitalizado de poucas paginas ja ultrapassa 64 KB com folga. O limite
    efetivo e o menor entre `baixa_anexo_max_mb` (configuracao) e o
    `max_allowed_packet` do servidor MySQL (R-14).

    `sha256` permite verificar integridade e detectar anexo corrompido sem
    abrir o arquivo.
    """
    __tablename__ = "baixa_documento"

    id:             Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_original:  Mapped[str]      = mapped_column(String(160), nullable=False)
    tamanho_bytes:  Mapped[int]      = mapped_column(Integer, nullable=False)
    sha256:         Mapped[str]      = mapped_column(CHAR(64), nullable=False)
    conteudo:       Mapped[bytes]    = mapped_column(MEDIUMBLOB, nullable=False)
    anexado_em:     Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    anexado_por:    Mapped[int]      = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship(foreign_keys=[anexado_por])

    __table_args__ = (
        Index('idx_baixa_doc_sha256', 'sha256'),
        Index('idx_baixa_doc_usuario', 'anexado_por'),
    )

    def __repr__(self):
        return f"<BaixaDocumento {self.nome_original} | {self.tamanho_bytes} bytes>"


class ManutencaoBem(Base):
    """
    Tabela: manutencao_bem — MOD-07 (v1.8 · RF-38)

    Historico de manutencoes realizadas no bem. Tabela SOMENTE INCREMENTAL
    (RN-23): novo registro nao substitui os anteriores, e registros
    existentes nao sao editados nem excluidos.

    NENHUM campo de manutencao existe em `bem_patrimonial` (AD-24). Manter a
    ultima manutencao copiada la introduziria risco de dessincronia sem
    beneficio. A data exibida na listagem T-23 sai de agregacao em consulta
    unica:

        SELECT b.*, m.ultima
          FROM bem_patrimonial b
          LEFT JOIN (SELECT bem_id, MAX(data_manutencao) AS ultima
                       FROM manutencao_bem GROUP BY bem_id) m
            ON m.bem_id = b.id

    O indice (bem_id, data_manutencao) cobre essa agregacao — o plano de
    execucao usa varredura solta do indice, sem tocar na tabela — e tambem a
    listagem cronologica da T-29.

    Manutencao NAO gera linha em `movimentacao_bem`: o ENUM de `tipo`
    daquela tabela permanece restrito a cadastro, transferencia, ajuste de
    inventario e baixa. As duas tabelas de historico tem propositos
    distintos e nao se misturam.
    """
    __tablename__ = "manutencao_bem"

    id:               Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    bem_id:           Mapped[int]      = mapped_column(Integer, ForeignKey("bem_patrimonial.id"), nullable=False)
    data_manutencao:  Mapped[date]     = mapped_column(Date, nullable=False)
    descricao:        Mapped[str]      = mapped_column(String(500), nullable=False)
    usuario_id:       Mapped[int]      = mapped_column(Integer, ForeignKey("usuario.id"), nullable=False)
    registrado_em:    Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    bem:     Mapped["BemPatrimonial"] = relationship(back_populates="manutencoes")
    usuario: Mapped["Usuario"]        = relationship(foreign_keys=[usuario_id])

    __table_args__ = (
        Index('idx_manut_bem_data', 'bem_id', 'data_manutencao'),
        Index('idx_manut_usuario', 'usuario_id'),
    )

    def __repr__(self):
        return f"<ManutencaoBem bem {self.bem_id} | {self.data_manutencao}>"


class SchemaMigracao(Base):
    """
    Tabela: schema_migracao — infra

    Registro das migrações aplicadas (AD-20). Não é consumida pela aplicação:
    existe para tornar verificável, no próprio banco, quais scripts rodaram.
    """
    __tablename__ = "schema_migracao"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    versao:       Mapped[str]      = mapped_column(String(60),  nullable=False)
    descricao:    Mapped[str]      = mapped_column(String(255), nullable=False)
    aplicada_em:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index('uq_schema_migracao_versao', 'versao', unique=True),
    )

    def __repr__(self):
        return f"<SchemaMigracao {self.versao} em {self.aplicada_em}>"
