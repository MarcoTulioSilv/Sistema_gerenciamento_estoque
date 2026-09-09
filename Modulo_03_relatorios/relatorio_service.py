"""
Modulo_03_relatorios · relatorio_service.py
Sprint 4 — RelatorioService: gera, envia e agenda relatórios XLSX.
"""
import logging
from sqlalchemy.orm import joinedload
from datetime import datetime as dt
from datetime import date, datetime, time, timedelta
from pathlib  import Path
from .xlsx_builder import (
    XlsxBuilder, _TIPO_MOV_HUMANIZADO,
    SITUACAO_NORMAL, SITUACAO_ATENCAO, SITUACAO_VENCIDO,
    URGENCIA_CRITICO, URGENCIA_URGENTE, URGENCIA_ATENCAO,
)
from .grupo_consumo_repo import GrupoConsumoRepo
from fuso_horario import formatar
from Modulo_04_notificacoes.gmail_client import GmailClient
from Modulo_06_dados import (
    get_read_session, RelatorioAgendamento, get_session, JobLog, GrupoConsumo,
    Movimentacao, Lote, Produto, Usuario, TipoMovimentacaoEnum, CentroAlocacaoEnum,
)

logger = logging.getLogger(__name__)
 
 
class RelatorioService:
    """
    Orquestra a geração de XLSX e o envio por Gmail.
    Usado por T-11 (sob demanda) e pelo scheduler (agendamento).
    """
 
    # ── Geração + envio sob demanda (RF-20) ───────────────────────────────
 
    @staticmethod
    def gerar_movimentacao(data_ini: date, data_fim: date, tipos: list[str] | None = None,
                           usuario_ids: list[int] | None = None, termo: str | None = None) -> Path:
        """Gera o XLSX de movimentação sem enviar e-mail (usado por e-mail e download)."""
        return XlsxBuilder.movimentacao(data_ini, data_fim, tipos, usuario_ids, termo)

    @staticmethod
    def gerar_e_enviar_movimentacao(data_ini: date, data_fim: date, tipos: list[str] | None = None,
                                    usuario_ids: list[int] | None = None, termo: str | None = None) -> Path:
        """RF-15: gera relatório de movimentação (filtrado, se informado) e envia por e-mail."""
        caminho = RelatorioService.gerar_movimentacao(data_ini, data_fim, tipos, usuario_ids, termo)
        assunto = (f"SCE — Relatório de Movimentação "
                   f"{data_ini.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        corpo = _html_corpo(
            titulo  = "Relatório de Movimentação",
            descricao = (f"Período: {data_ini.strftime('%d/%m/%Y')} "
                         f"a {data_fim.strftime('%d/%m/%Y')}"),
            rodape  = "Arquivo XLSX anexado a este e-mail.",
        )
        GmailClient.enviar(assunto, corpo, anexos=[caminho])
        _registrar_envio("movimentacao")
        return caminho

    @staticmethod
    def gerar_estoque_atual(centros: list[str] | None = None,
                            situacoes: list[str] | None = None,
                            termo: str | None = None) -> Path:
        """Gera o XLSX de estoque atual sem enviar e-mail (usado por e-mail e download)."""
        return XlsxBuilder.estoque_atual(centros, situacoes, termo)

    @staticmethod
    def gerar_e_enviar_estoque_atual(centros: list[str] | None = None,
                                     situacoes: list[str] | None = None,
                                     termo: str | None = None) -> Path:
        """RF-16: gera relatório de estoque atual (filtrado, se informado) e envia por e-mail."""
        caminho = RelatorioService.gerar_estoque_atual(centros, situacoes, termo)
        assunto = f"SCE — Relatório de Estoque Atual — {date.today().strftime('%d/%m/%Y')}"
        corpo   = _html_corpo(
            titulo    = "Relatório de Estoque Atual",
            descricao = f"Posição do estoque em {date.today().strftime('%d/%m/%Y')}.",
            rodape    = "Arquivo XLSX anexado. Lotes vencidos estão marcados em vermelho.",
        )
        GmailClient.enviar(assunto, corpo, anexos=[caminho])
        _registrar_envio("estoque_atual")
        return caminho

    @staticmethod
    def gerar_a_vencer(dias: int = 30, centros: list[str] | None = None,
                       urgencias: list[str] | None = None, termo: str | None = None) -> Path:
        """Gera o XLSX de produtos a vencer sem enviar e-mail (usado por e-mail e download)."""
        return XlsxBuilder.a_vencer(dias, centros, urgencias, termo)

    @staticmethod
    def gerar_e_enviar_a_vencer(dias: int = 30, centros: list[str] | None = None,
                                urgencias: list[str] | None = None, termo: str | None = None) -> Path:
        """RF-17: gera relatório de produtos a vencer (filtrado, se informado) e envia por e-mail."""
        caminho = RelatorioService.gerar_a_vencer(dias, centros, urgencias, termo)
        assunto = f"SCE — Lotes a Vencer nos Próximos {dias} Dias"
        corpo   = _html_corpo(
            titulo    = f"Lotes a Vencer — Próximos {dias} dias",
            descricao = f"Relatório gerado em {date.today().strftime('%d/%m/%Y')}.",
            rodape    = "Arquivo XLSX anexado. Itens críticos marcados em vermelho.",
        )
        GmailClient.enviar(assunto, corpo, anexos=[caminho])
        _registrar_envio("a_vencer")
        return caminho

    @staticmethod
    def gerar_lotes_vencidos(centros: list[str] | None = None, termo: str | None = None) -> Path:
        """Gera o XLSX de lotes vencidos sem enviar e-mail (usado por e-mail e download)."""
        return XlsxBuilder.lotes_vencidos(centros, termo)

    @staticmethod
    def gerar_e_enviar_lotes_vencidos(centros: list[str] | None = None, termo: str | None = None) -> Path:
        """RF-22: gera relatório de lotes vencidos (filtrado, se informado) e envia por e-mail."""
        caminho = RelatorioService.gerar_lotes_vencidos(centros, termo)
        if caminho is None:
            return None
        assunto = f"SCE — ⚠ Lotes Vencidos em Estoque — {date.today().strftime('%d/%m/%Y')}"
        corpo   = _html_corpo(
            titulo    = "⚠ Lotes Vencidos em Estoque",
            descricao = (f"Atenção: existem lotes com data de vencimento anterior a hoje "
                         f"com saldo em estoque. Providencie o descarte imediato."),
            rodape    = "Arquivo XLSX com todos os lotes vencidos anexado.",
            alerta    = True,
        )
        GmailClient.enviar(assunto, corpo, anexos=[caminho])
        _registrar_envio("lotes_vencidos")
        return caminho

    @staticmethod
    def gerar_consumo_medio(meses: int, termo: str | None = None) -> Path:
        """
        Gera o relatório de consumo médio (sem enviar e-mail — usado por
        e-mail e download). `termo` — mesma busca textual da caixa de
        pesquisa em T-11 (aplicada aqui, não na consulta, já que os dados
        já vêm agregados por rótulo/mês de `buscar_dados_consumo_medio`).
        """
        rotulos_meses, dados = RelatorioService.buscar_dados_consumo_medio(meses)
        if termo:
            termo_lower = termo.strip().lower()
            dados = [linha for linha in dados if any(termo_lower in str(v).lower() for v in linha)]
        return XlsxBuilder.consumo_medio(dados, rotulos_meses)

    @staticmethod
    def enviar_consumo_medio(meses: int, termo: str | None = None) -> Path:
        """Gera o relatório de consumo médio e envia por e-mail. Sob demanda — sem agendamento."""
        caminho = RelatorioService.gerar_consumo_medio(meses, termo)
        assunto = f"SCE — Consumo Médio por Produto (últimos {meses} meses)"
        corpo   = _html_corpo(
            titulo    = "Consumo Médio por Produto",
            descricao = f"Consumo total e média mensal dos últimos {meses} meses, por produto ativo.",
            rodape    = "Arquivo XLSX anexado.",
        )
        GmailClient.enviar(assunto, corpo, anexos=[caminho])
        return caminho

    #── Busca de dados para exibição na UI ───────────────────────────────────────────────
    @staticmethod
    def buscar_dados_movimentacao(data_ini: date, data_fim: date, tipos: list[str] | None = None,
                                  usuario_ids: list[int] | None = None) -> list[list]:
        """Retorna os dados puros de movimentação (filtrados, se informado) para a tabela visual da UI."""

        inicio = dt.combine(data_ini, dt.min.time())
        fim    = dt.combine(data_fim, dt.max.time())

        with get_read_session() as s:
            query = (
                s.query(Movimentacao)
                .join(Lote).join(Produto).join(Usuario)
                .options(
                    joinedload(Movimentacao.lote).joinedload(Lote.produto),
                    joinedload(Movimentacao.usuario),
                )
                .filter(Movimentacao.data_hora.between(inicio, fim))
            )
            if tipos:
                enums = [_TIPO_MOV_HUMANIZADO[t] for t in tipos if t in _TIPO_MOV_HUMANIZADO]
                if enums:
                    query = query.filter(Movimentacao.tipo.in_(enums))
            if usuario_ids:
                query = query.filter(Movimentacao.usuario_id.in_(usuario_ids))
            movs = query.order_by(Movimentacao.data_hora.desc()).all()
            return [
                [
                    formatar(m.data_hora, "%d/%m/%Y %H:%M"),
                    m.lote.produto.nome,
                    m.lote.num_lote,
                    m.lote.unidade_estoque.value,
                    m.numero_nf or m.lote.nota_fiscal or "—",
                    m.tipo.value.replace("_", " ").title(),
                    m.quantidade,
                    m.usuario.nome,
                    m.observacao or "",
                    
                ] for m in movs
            ]

    @staticmethod
    def mapear_usuarios_movimentacao(data_ini: date, data_fim: date) -> dict[str, int]:
        """
        {nome: usuario_id} de quem tem ao menos uma movimentação no período —
        usado por T-11 para traduzir o filtro de Usuário (mostra nome,
        checkbox) em usuario_ids antes de chamar gerar_movimentacao/
        gerar_e_enviar_movimentacao. Mesmo critério de população do combo
        antigo: só usuários que aparecem no período, não todo o cadastro.
        """
        inicio = dt.combine(data_ini, dt.min.time())
        fim    = dt.combine(data_fim, dt.max.time())
        with get_read_session() as s:
            linhas = (
                s.query(Usuario.nome, Usuario.id)
                .join(Movimentacao, Movimentacao.usuario_id == Usuario.id)
                .filter(Movimentacao.data_hora.between(inicio, fim))
                .distinct()
                .all()
            )
            return {nome: id_ for nome, id_ in linhas}
    @staticmethod
    def buscar_dados_estoque_atual(centros: list[str] | None = None,
                                   situacoes: list[str] | None = None) -> list[list]:
        """Retorna a posição do estoque (filtrada, se informado) para exibição na UI."""

        hoje = date.today()
        with get_read_session() as s:
            query = (
                s.query(Lote).join(Produto)
                .options(joinedload(Lote.produto))
                .filter(Produto.ativo == True, Lote.quantidade_atual > 0)
            )
            if centros:
                enums = [CentroAlocacaoEnum(c.lower()) for c in centros]
                query = query.filter(Lote.centro_alocacao.in_(enums))
            lotes = query.order_by(Produto.nome, Lote.data_vencimento).all()
            dados = []
            for l in lotes:
                vencido = False if l.data_vencimento is None else l.data_vencimento < hoje
                diff = None if l.data_vencimento is None else (l.data_vencimento - hoje).days

                if diff is None: sit = SITUACAO_NORMAL
                elif vencido: sit = SITUACAO_VENCIDO
                elif diff <= 15: sit = SITUACAO_ATENCAO
                else: sit = SITUACAO_NORMAL

                if situacoes and sit not in situacoes:
                    continue

                dados.append([
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.num_lote,
                    l.unidade_estoque.value,
                    l.nota_fiscal or "—",
                    l.data_fabricacao.strftime("%d/%m/%Y") if l.data_fabricacao else "—",
                    l.data_vencimento.strftime("%d/%m/%Y") if l.data_vencimento else "—",
                    l.quantidade_inicial,
                    l.quantidade_atual,
                    f"R$ {float(l.valor_unitario):,.2f}",
                    f"R$ {float(l.valor_total):,.2f}",
                    sit,
                    
                ])
            return dados

    @staticmethod
    def buscar_dados_a_vencer(dias: int = 30, centros: list[str] | None = None,
                              urgencias: list[str] | None = None) -> list[list]:
        """Retorna produtos próximos ao vencimento (filtrados, se informado) para a UI."""

        hoje = date.today()
        limite = hoje + timedelta(days=dias)
        with get_read_session() as s:
            query = (
                s.query(Lote).join(Produto)
                .options(joinedload(Lote.produto))
                .filter(
                    Produto.ativo == True, Lote.quantidade_atual > 0,
                    Lote.data_vencimento >= hoje, Lote.data_vencimento <= limite,
                    Lote.data_vencimento.isnot(None),
                )
            )
            if centros:
                enums = [CentroAlocacaoEnum(c.lower()) for c in centros]
                query = query.filter(Lote.centro_alocacao.in_(enums))
            lotes = query.order_by(Lote.data_vencimento).all()

            dados = []
            for l in lotes:
                diff = (l.data_vencimento - hoje).days
                if diff <= 2: urgencia = URGENCIA_CRITICO
                elif diff <= 7: urgencia = URGENCIA_URGENTE
                else: urgencia = URGENCIA_ATENCAO

                if urgencias and urgencia not in urgencias:
                    continue

                dados.append([
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.num_lote,
                    l.unidade_estoque.value,
                    l.nota_fiscal or "—",
                    l.data_vencimento.strftime("%d/%m/%Y"),
                    f"{diff} dias",
                    l.quantidade_atual,
                    urgencia,
                    
                ])
            return dados

    @staticmethod
    def buscar_dados_lotes_vencidos(centros: list[str] | None = None) -> list[list]:
        """Retorna os lotes vencidos (filtrados, se informado) para a UI."""

        hoje = date.today()
        with get_read_session() as s:
            query = (
                s.query(Lote).join(Produto)
                .options(joinedload(Lote.produto))
                .filter(
                    Produto.ativo == True, Lote.quantidade_atual > 0,
                    Lote.data_vencimento < hoje, Lote.data_vencimento.isnot(None),
                )
            )
            if centros:
                enums = [CentroAlocacaoEnum(c.lower()) for c in centros]
                query = query.filter(Lote.centro_alocacao.in_(enums))
            lotes = query.order_by(Lote.data_vencimento).all()
            return [
                [
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.produto.fornecedor or "—",
                    l.num_lote,
                    l.nota_fiscal or "—",
                    l.data_vencimento.strftime("%d/%m/%Y"),
                    f"{(hoje - l.data_vencimento).days} dias",
                    l.quantidade_atual,
                    f"R$ {float(l.valor_unitario * l.quantidade_atual):,.2f}"
                ] for l in lotes
            ]

    @staticmethod
    def buscar_dados_consumo_medio(meses: int) -> tuple[list[str], list[list]]:
        """
        Consumo (saídas) mês a mês dos últimos `meses` meses de calendário,
        agrupado por grupo de consumo (GrupoConsumo — produtos "irmãos" com
        palavras-chave em comum) ou pelo próprio produto, se não pertencer a
        nenhum grupo. Inclui grupos/produtos sem nenhuma saída no período
        (aparecem com 0) — visão geral do catálogo ativo.

        Retorna (rótulos_dos_meses, linhas), onde cada linha é
        [rótulo, mês1, mês2, ..., mêsN, total, média_mensal].
        """
        hoje     = date.today()
        periodos = _ultimos_n_meses(meses, hoje)  # mais antigo -> mais recente
        rotulos_meses = [label for _, _, label in periodos]

        with get_read_session() as s:
            produtos = (
                s.query(Produto.id, Produto.nome)
                .filter(Produto.ativo == True)
                .all()
            )
            grupos = s.query(GrupoConsumo).order_by(GrupoConsumo.id).all()
            s.expunge_all()

            # Resolve produto_id -> rótulo da linha (nome do grupo ou do próprio produto).
            # Primeiro grupo cadastrado que bater (todas as palavras-chave) vence.
            grupos_parsed = [
                (g.nome, [t.strip().lower() for t in g.termos_chave.split(",") if t.strip()])
                for g in grupos
            ]
            produto_rotulo: dict[int, str] = {}
            for pid, nome in produtos:
                nome_lower = nome.lower()
                rotulo = nome
                for nome_grupo, termos in grupos_parsed:
                    if termos and all(termo in nome_lower for termo in termos):
                        rotulo = nome_grupo
                        break
                produto_rotulo[pid] = rotulo

            # Todas as movimentações do período inteiro, numa única query.
            inicio_total = dt.combine(periodos[0][0], dt.min.time())
            fim_total    = dt.combine(periodos[-1][1], dt.max.time())
            movs = (
                s.query(Movimentacao.data_hora, Movimentacao.quantidade, Lote.produto_id)
                .join(Lote, Lote.id == Movimentacao.lote_id)
                .filter(
                    Movimentacao.tipo == TipoMovimentacaoEnum.saida,
                    Movimentacao.data_hora.between(inicio_total, fim_total),
                )
                .all()
            )

        rotulos_presentes = sorted(set(produto_rotulo.values()))
        acumulado: dict[str, list[int]] = {r: [0] * meses for r in rotulos_presentes}

        # Data da saída mais antiga já registrada no sistema — aproxima o
        # início real de produção do SCE. Sem isso, meses anteriores à entrada
        # em produção entrariam como "consumo zero" e derrubariam a média
        # artificialmente (o sistema não existia, não é que não houve consumo).
        data_inicio_sistema = min((dh.date() for dh, _, _ in movs), default=None)

        for data_hora, quantidade, produto_id in movs:
            rotulo = produto_rotulo.get(produto_id)
            if rotulo is None:
                continue  # produto inativo — fora do relatório
            data_mov = data_hora.date()
            for idx, (ini, fim, _) in enumerate(periodos):
                if ini <= data_mov <= fim:
                    acumulado[rotulo][idx] += quantidade
                    break

        # Meses inteiramente anteriores ao início real de produção não contam
        # no total/média (não têm dado real — nem "zero" de verdade).
        meses_validos = [
            idx for idx, (_, fim, _) in enumerate(periodos)
            if data_inicio_sistema is not None and fim >= data_inicio_sistema
        ]
        qtd_meses_validos = len(meses_validos) or 1  # evita divisão por zero

        linhas = []
        for rotulo in rotulos_presentes:
            valores_mes = acumulado[rotulo]
            total = sum(valores_mes[idx] for idx in meses_validos)
            media = round(total / qtd_meses_validos, 1)
            valores_exibicao = [
                valores_mes[idx] if idx in meses_validos else "—"
                for idx in range(meses)
            ]
            linhas.append([rotulo, *valores_exibicao, total, media])

        return rotulos_meses, linhas

    @staticmethod
    def rotulos_meses_consumo(meses: int) -> list[str]:
        """Rótulos dos últimos `meses` meses de calendário (monta as colunas na UI sem ir ao banco)."""
        return [label for _, _, label in _ultimos_n_meses(meses, date.today())]

    # ── Grupos de consumo (agrupamento por palavra-chave para consumo médio) ──

    @staticmethod
    def listar_grupos_consumo() -> list[GrupoConsumo]:
        return GrupoConsumoRepo.listar()

    @staticmethod
    def criar_grupo_consumo(nome: str, termos: list[str]) -> None:
        nome = nome.strip()
        if not nome:
            raise ValueError("Nome do grupo é obrigatório.")
        termos_limpos = [t.strip() for t in termos if t.strip()]
        if not termos_limpos:
            raise ValueError("Informe ao menos uma palavra-chave.")
        if GrupoConsumoRepo.buscar_por_nome(nome):
            raise ValueError(f"Já existe um grupo chamado '{nome}'.")
        GrupoConsumoRepo.criar(nome, ", ".join(termos_limpos))
        logger.info("Grupo de consumo criado: %s (%s)", nome, termos_limpos)

    @staticmethod
    def editar_grupo_consumo(id_: int, nome: str, termos: list[str]) -> None:
        nome = nome.strip()
        if not nome:
            raise ValueError("Nome do grupo é obrigatório.")
        termos_limpos = [t.strip() for t in termos if t.strip()]
        if not termos_limpos:
            raise ValueError("Informe ao menos uma palavra-chave.")
        existente = GrupoConsumoRepo.buscar_por_nome(nome)
        if existente and existente.id != id_:
            raise ValueError(f"Já existe um grupo chamado '{nome}'.")
        GrupoConsumoRepo.atualizar(id_, nome, ", ".join(termos_limpos))
        logger.info("Grupo de consumo editado: id=%s -> %s (%s)", id_, nome, termos_limpos)

    @staticmethod
    def remover_grupo_consumo(id_: int) -> None:
        GrupoConsumoRepo.remover(id_)
        logger.info("Grupo de consumo removido: id=%s", id_)

    # ── Agendamento (RF-21) ───────────────────────────────────────────────
 
    @staticmethod
    def listar_agendamentos() -> list:
        """Retorna todos os registros de relatorio_agendamento."""
        
        with get_read_session() as s:
            items = s.query(RelatorioAgendamento).order_by(
                RelatorioAgendamento.tipo_relatorio).all()
            s.expunge_all()
            return items
 
    @staticmethod
    def salvar_agendamento(tipo: str, habilitado: bool,
                           periodicidade: str, horario: time) -> None:
        """Atualiza um agendamento na tabela relatorio_agendamento."""
        with get_session() as s:
            ag = s.query(RelatorioAgendamento).filter_by(
                tipo_relatorio=tipo).first()
            if ag:
                ag.habilitado    = habilitado
                ag.periodicidade = periodicidade
                ag.horario       = horario
            else:
                s.add(RelatorioAgendamento(
                    tipo_relatorio = tipo,
                    habilitado     = habilitado,
                    periodicidade  = periodicidade,
                    horario        = horario,
                ))
        logger.info("Agendamento salvo: %s | %s | %s | %s",
                    tipo, habilitado, periodicidade, horario)
 
    @staticmethod
    def executar_agendados() -> None:
        """
        Chamado pelo scheduler (APScheduler) para executar relatórios agendados.
        Verifica periodicidade e último envio antes de gerar.
        Registra resultado em job_log independentemente do sucesso (RNF-08).
        """
        hoje = date.today()
 
        with get_read_session() as s:
            agendamentos = s.query(RelatorioAgendamento).filter_by(
                habilitado=True).all()
            s.expunge_all()
 
        for ag in agendamentos:
            if not _deve_executar(ag, hoje):
                continue
 
            sucesso = True
            detalhe = ""
            try:
                _executar_tipo(ag.tipo_relatorio)
                _registrar_envio(ag.tipo_relatorio)
                logger.info("Relatório agendado executado: %s", ag.tipo_relatorio)
            except Exception as exc:
                sucesso = False
                detalhe = str(exc)[:255]
                logger.error("Falha no relatório agendado '%s': %s",
                             ag.tipo_relatorio, exc)
 
            # Grava job_log independente do resultado (RNF-08)
            with get_session() as s:
                s.add(JobLog(
                    job_nome     = f"relatorio_{ag.tipo_relatorio}",
                    executado_em = datetime.utcnow(),
                    sucesso      = sucesso,
                    detalhe      = detalhe or None,
                ))
 
 
# ── Utilitários internos ──────────────────────────────────────────────────────

_NOMES_MES = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
              "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _ultimos_n_meses(n: int, hoje: date) -> list[tuple[date, date, str]]:
    """
    Últimos `n` meses de calendário FECHADOS (mais antigo -> mais recente),
    cada um como (inicio, fim, rótulo "Mmm/AAAA"). O mês em andamento nunca
    entra — só meses já encerrados, para não puxar a média para baixo com
    um mês parcial (ex.: só 10 dias de saída contando como mês cheio).
    """
    periodos = []
    mes, ano = hoje.month - 1, hoje.year
    if mes == 0:
        mes, ano = 12, ano - 1
    for i in range(n):
        m, a = mes - i, ano
        while m <= 0:
            m += 12
            a -= 1
        inicio = date(a, m, 1)
        prox = date(a + 1, 1, 1) if m == 12 else date(a, m + 1, 1)
        fim = prox - timedelta(days=1)
        periodos.append((inicio, fim, f"{_NOMES_MES[m]}/{a}"))
    periodos.reverse()
    return periodos


def _executar_tipo(tipo: str) -> None:
    """Despacha para o método correto conforme tipo de relatório."""
    hoje = date.today()
    despacho = {
        "movimentacao":   lambda: RelatorioService.gerar_e_enviar_movimentacao(
            date(hoje.year, hoje.month, 1), hoje),
        "estoque_atual":  RelatorioService.gerar_e_enviar_estoque_atual,
        "a_vencer":       RelatorioService.gerar_e_enviar_a_vencer,
        "lotes_vencidos": RelatorioService.gerar_e_enviar_lotes_vencidos,
    }
    fn = despacho.get(tipo)
    if fn:
        fn()
    else:
        raise ValueError(f"Tipo de relatório desconhecido: {tipo}")
 
 
def _deve_executar(ag, hoje: date) -> bool:
    """Verifica se o agendamento deve rodar hoje com base na periodicidade."""
    if ag.ultimo_envio is None:
        return True
    ultimo = ag.ultimo_envio.date()
    if ag.periodicidade == "diario":
        return ultimo < hoje
    if ag.periodicidade == "semanal":
        return (hoje - ultimo).days >= 7
    if ag.periodicidade == "mensal":
        return (hoje-ultimo).days >= 30
    return False
 
 
def _registrar_envio(tipo: str) -> None:
    """Atualiza ultimo_envio no agendamento após envio bem-sucedido."""
    try:
        with get_session() as s:
            ag = s.query(RelatorioAgendamento).filter_by(
                tipo_relatorio=tipo).first()
            if ag:
                ag.ultimo_envio = datetime.utcnow()
    except Exception as exc:
        logger.warning("Erro ao atualizar ultimo_envio para '%s': %s", tipo, exc)
 
 
def _html_corpo(titulo: str, descricao: str, rodape: str,
                alerta: bool = False) -> str:
    """Gera corpo HTML padronizado para os e-mails de relatório."""
    cor_borda = "#A32D2D" if alerta else "#1F4E79"
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#3d3d3a;padding:20px">
      <div style="max-width:600px;margin:0 auto;border:2px solid {cor_borda};
                  border-radius:8px;overflow:hidden">
        <div style="background:{cor_borda};padding:16px 20px">
          <h2 style="color:#fff;margin:0;font-size:18px">{titulo}</h2>
        </div>
        <div style="padding:20px">
          <p style="font-size:14px;line-height:1.6">{descricao}</p>
          <hr style="border:none;border-top:1px solid #E8E6DE;margin:16px 0">
          <p style="font-size:12px;color:#888780">{rodape}</p>
          <p style="font-size:11px;color:#AAAAAA;margin-top:20px">
            Sistema de Controle de Estoque — Centro de Uro-Nefrologia<br>
            Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}
          </p>
        </div>
      </div>
    </body></html>
    """