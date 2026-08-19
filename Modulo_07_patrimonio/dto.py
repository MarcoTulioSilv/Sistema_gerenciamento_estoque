"""
MOD-07 · Modulo_07_patrimonio · dto.py

Objetos de transferência entre os serviços do MOD-07 e seus consumidores
(telas T-23 a T-27 e serviço HTTP de coleta).

POR QUE DTOs E NÃO SÓ ENTIDADES ORM
    Entidades (BemPatrimonial, Inventario) continuam sendo devolvidas
    diretamente pelos métodos de consulta, seguindo o padrão do projeto —
    os repos fazem expunge_all() antes de entregá-las.

    Os DTOs existem para o que NÃO é entidade: resultados calculados,
    filtros e comandos. Devolver um dicionário solto nesses casos empurra
    para a GUI o trabalho de adivinhar chaves.

Todos os DTOs são imutáveis (frozen=True), exceto os de entrada.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


# ─── Enums de resultado ─────────────────────────────────────────────────────

class ClassificacaoLeitura(str, enum.Enum):
    """
    Resultado da árvore de decisão de registrar_leitura (ERS §3.2).

    Ordem de avaliação, do mais específico ao mais genérico:
      1. codigo_ilegivel        — não resolve para tombo algum
      2. bem_baixado            — tombo existe, mas bem está baixado
      3. ja_conferido           — item já lido nesta sessão (RN-20)
      4. encontrado             — item da sessão, na localização esperada
      5. divergente_local       — item da sessão, em outra localização
      6. sobra_outra_sessao     — bem pertence a outra sessão aberta (RN-18)
      7. sobra_fora_escopo      — bem cadastrado, fora de qualquer sessão
      8. sobra_nao_cadastrado   — tombo válido em forma, inexistente
    """
    encontrado           = "encontrado"
    divergente_local     = "divergente_local"
    ja_conferido         = "ja_conferido"
    sobra_outra_sessao   = "sobra_outra_sessao"
    sobra_fora_escopo    = "sobra_fora_escopo"
    sobra_nao_cadastrado = "sobra_nao_cadastrado"
    bem_baixado          = "bem_baixado"
    codigo_ilegivel      = "codigo_ilegivel"


class SeveridadeLeitura(str, enum.Enum):
    """
    Realimentação visual e sonora da tela de coleta e da página móvel.
    Mapeamento fixo, para que estação e celular se comportem igual.
    """
    ok       = "ok"       # verde  — encontrado, ja_conferido
    atencao  = "atencao"  # âmbar  — divergente_local, sobra_*
    erro     = "erro"     # vermelho — bem_baixado, codigo_ilegivel


class CodigoAviso(str, enum.Enum):
    """
    Avisos que não impedem a operação, mas exigem ciência do usuário.

    Existem como código, e não apenas como texto, para que a GUI possa
    decidir o tratamento (banner, destaque, confirmação extra) sem depender
    de comparar strings de mensagem.
    """
    escopo_vazio = "escopo_vazio"


class SaidaEtiqueta(str, enum.Enum):
    """Caminhos de emissão de etiqueta (RF-28.1 a RF-28.3)."""
    impressora_rede  = "impressora_rede"
    impressora_cabo  = "impressora_cabo"
    arquivo_unitario = "arquivo_unitario"   # uma etiqueta por página, 100×50 mm
    arquivo_folha    = "arquivo_folha"      # A4 em grade, com marcas de corte


# ─── Entrada ────────────────────────────────────────────────────────────────

@dataclass
class FiltroBens:
    """Filtros da listagem de bens (T-23). Campos None são ignorados."""
    texto: str | None = None                 # busca em tombo e descrição
    localizacao_id: int | None = None
    situacao: str | None = None
    apenas_ativos: bool = True
    ordenar_por: str = "tombo"               # tombo | descricao | localizacao
    limite: int | None = None


@dataclass
class DadosBem:
    """
    Payload de cadastro e edição (RF-25).

    O tombo NÃO aparece aqui: é emitido pelo sistema (RF-26) e imutável
    depois (RN-09). Permitir que a GUI o envie seria abrir caminho para
    violá-lo.
    """
    descricao: str
    localizacao_id: int
    marca_modelo: str | None = None
    data_aquisicao: date | None = None
    valor_aquisicao: Decimal | None = None
    nota_fiscal: str | None = None
    observacao: str | None = None


@dataclass
class DadosManutencao:
    """Payload de registro de manutenção realizada em um bem (RF-38, RN-23)."""
    data_manutencao: date
    descricao: str


@dataclass
class DadosBaixa:
    """
    Payload de baixa patrimonial (RF-30, v1.8).

    O anexo em PDF é obrigatório (validado no serviço antes de qualquer
    escrita, RNF-20) — `anexo_conteudo`/`anexo_nome` não têm default.
    `documento` é a referência textual livre (ata/termo/processo) já
    existente antes da v1.8, independente do anexo e do MTR/laudo.
    """
    motivo: str
    data_baixa: date
    anexo_conteudo: bytes
    anexo_nome: str
    numero_mtr: str | None = None
    numero_laudo: str | None = None
    documento: str | None = None
    observacao: str | None = None


@dataclass(frozen=True)
class ContextoColeta:
    """
    Contexto resolvido a partir do token de pareamento (RF-36).

    Responde às três perguntas que o código lido não responde: em qual
    sessão registrar, em qual localização o operador está e quem é ele.
    O mesmo DTO é montado pela estação a partir da seleção em tela, de modo
    que registrar_leitura não precisa saber a origem da leitura.
    """
    inventario_id: int
    localizacao_id: int
    usuario_id: int
    origem: str = "estacao"                  # estacao | movel
    token_id: int | None = None
    dispositivo_label: str | None = None


@dataclass(frozen=True)
class AjusteConfirmado:
    """
    Decisão do usuário sobre uma divergência, no fechamento (RN-14).

    aplicar=True move o bem para a localização encontrada, gerando
    movimentação do tipo ajuste_inventario vinculada à sessão.
    aplicar=False mantém o cadastro e registra a recusa na observação.
    """
    inventario_item_id: int
    aplicar: bool
    observacao: str | None = None


# ─── Saída ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoLeitura:
    """
    Retorno de registrar_leitura. Contém tudo que a tela e a página móvel
    precisam exibir, sem consulta adicional.
    """
    classificacao: ClassificacaoLeitura
    severidade: SeveridadeLeitura
    mensagem: str                            # texto pronto para exibição
    codigo_lido: str
    tombo: str | None = None
    descricao_bem: str | None = None
    localizacao_esperada: str | None = None  # rótulo, não id
    localizacao_lida: str | None = None
    conferido_em: datetime | None = None     # preenchido em ja_conferido
    conferido_por: str | None = None
    total_esperado: int = 0
    total_conferido: int = 0

    @property
    def progresso(self) -> float:
        """Fração conferida da sessão, para a barra da tela de coleta."""
        if self.total_esperado == 0:
            return 0.0
        return self.total_conferido / self.total_esperado


@dataclass(frozen=True)
class ResumoSessao:
    """Consolidação de uma sessão, usada na coleta e no fechamento."""
    inventario_id: int
    descricao: str
    escopo: str
    localizacao: str | None
    status: str
    aberto_em: datetime
    total_esperado: int = 0
    pendentes: int = 0
    encontrados: int = 0
    divergentes: int = 0
    nao_localizados: int = 0
    sobras: int = 0

    @property
    def conferidos(self) -> int:
        return self.encontrados + self.divergentes

    @property
    def progresso(self) -> float:
        if self.total_esperado == 0:
            return 0.0
        return self.conferidos / self.total_esperado

    @property
    def pronta_para_fechar(self) -> bool:
        """
        Sessão pode ser fechada a qualquer momento — pendentes viram
        nao_localizado (RN-15). Esta propriedade indica apenas se a coleta
        foi concluída, para a tela poder alertar antes de fechar cedo demais.
        """
        return self.pendentes == 0


@dataclass(frozen=True)
class Aviso:
    """Aviso não bloqueante devolvido por um serviço."""
    codigo: CodigoAviso
    mensagem: str


@dataclass(frozen=True)
class ResultadoAbertura:
    """
    Retorno de abrir_sessao.

    A sessão é SEMPRE criada quando as regras permitem. Situações que
    merecem atenção do usuário — como escopo sem nenhum bem ativo — vêm em
    `avisos`, não como exceção: o sistema não decide pela gestora que a
    campanha não deveria existir.
    """
    inventario_id: int
    descricao: str
    total_esperado: int
    avisos: tuple[Aviso, ...] = ()

    @property
    def escopo_vazio(self) -> bool:
        """
        Sessão aberta sem nenhum item no snapshot. A coleta não terá o que
        conferir, e o fechamento será imediato.
        """
        return self.total_esperado == 0


@dataclass(frozen=True)
class ResultadoEtiquetas:
    """Retorno da emissão de etiquetas (RF-28)."""
    saida: SaidaEtiqueta
    quantidade: int
    caminho_arquivo: str | None = None       # None nas saídas de impressão
    tombos: list[str] = field(default_factory=list)
    aviso: str | None = None                 # ex.: impressora lenta, fila cheia


@dataclass(frozen=True)
class BemPublico:
    """
    Projeção somente leitura devolvida à página móvel de consulta (RF-37).

    Deliberadamente NÃO expõe valor de aquisição, nota fiscal nem id
    interno: a página é acessível a qualquer dispositivo da rede sem
    autenticação, e nada aqui deve ser sensível.
    """
    tombo: str
    descricao: str
    marca_modelo: str | None
    localizacao: str
    situacao: str
    baixado: bool = False
    ultima_manutencao: date | None = None
