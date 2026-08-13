"""
MOD-07 · Modulo_07_patrimonio · patrimonio_service.py

CONTRATO PÚBLICO — bens, localizações, movimentação, baixa e etiquetas.

Este arquivo define assinaturas, exceções e regras aplicadas. Os corpos
serão implementados no Sprint 9; o contrato é fechado antes para que telas,
serviço HTTP e testes possam ser escritos contra ele.

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

from datetime import date

from .dto import (
    BemPublico, DadosBem, FiltroBens, ResultadoEtiquetas, SaidaEtiqueta,
)


class PatrimonioService:
    """Fachada de MOD-07 para bens patrimoniais e etiquetagem."""

    # ─── Consulta ───────────────────────────────────────────────────────────

    def listar_bens(self, filtro: FiltroBens | None = None) -> list:
        """
        Lista bens conforme filtro. Devolve entidades BemPatrimonial já
        desanexadas da sessão (expunge_all no repo).

        Usada por T-23. Sem filtro, devolve apenas bens ativos — a listagem
        padrão não deve mostrar baixados, que só aparecem sob filtro
        explícito.
        """
        raise NotImplementedError

    def obter_bem(self, bem_id: int):
        """
        Raises:
            BemNaoEncontradoError
        """
        raise NotImplementedError

    def obter_por_tombo(self, tombo: str):
        """
        Busca pelo tombo, aceitando o valor com ou sem espaços em volta e
        insensível a caixa.

        Raises:
            BemNaoEncontradoError
        """
        raise NotImplementedError

    def historico_bem(self, bem_id: int) -> list:
        """
        Movimentações do bem em ordem cronológica, incluindo o cadastro
        inicial e a baixa. Histórico é append-only (RN-11): nunca há o que
        editar aqui, só o que ler.
        """
        raise NotImplementedError

    def consultar_publico(self, tombo: str) -> BemPublico:
        """
        Projeção para a página móvel de consulta (RF-37).

        Sem autenticação: acessível a qualquer dispositivo da rede interna
        que leia o QR. Por isso devolve BemPublico, que omite valor de
        aquisição, nota fiscal e id interno.

        Raises:
            BemNaoEncontradoError
        """
        raise NotImplementedError

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
        """
        raise NotImplementedError

    def editar_bem(self, bem_id: int, dados: DadosBem, usuario_id: int):
        """
        Edita campos descritivos. NÃO altera tombo (RN-09) nem localização —
        mudança de lotação é transferência, e gera histórico (RF-29).

        Se dados.localizacao_id diferir da atual, o método levanta
        MovimentacaoInvalidaError em vez de mover em silêncio: caso
        contrário a alteração escaparia do histórico.

        Raises:
            BemNaoEncontradoError, BemBaixadoError, MovimentacaoInvalidaError
        """
        raise NotImplementedError

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
            LocalizacaoNaoEncontradaError, MovimentacaoInvalidaError
        """
        raise NotImplementedError

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
        raise NotImplementedError

    # ─── Localizações ───────────────────────────────────────────────────────

    def listar_localizacoes(self, apenas_ativas: bool = True) -> list:
        """Localizações para combos de tela e escopo de sessão."""
        raise NotImplementedError

    def cadastrar_localizacao(self, setor: str, sala: str, usuario_id: int,
                              descricao: str | None = None):
        """
        Raises:
            PermissaoNegadaError  (somente ti)
        """
        raise NotImplementedError

    def editar_localizacao(self, localizacao_id: int, setor: str, sala: str,
                           usuario_id: int, descricao: str | None = None):
        """
        Raises:
            LocalizacaoNaoEncontradaError, PermissaoNegadaError
        """
        raise NotImplementedError

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
        raise NotImplementedError

    # ─── Etiquetas ──────────────────────────────────────────────────────────

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
