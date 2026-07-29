"""
Modulo_03_relatorios · relatorio_service.py
Sprint 4 — RelatorioService: gera, envia e agenda relatórios XLSX.
"""
import logging
from sqlalchemy.orm import joinedload
from datetime import datetime as dt
from datetime import date, datetime, time, timedelta
from pathlib  import Path
from .xlsx_builder import XlsxBuilder
from Modulo_04_notificacoes.gmail_client import GmailClient 
from Modulo_06_dados import get_read_session, RelatorioAgendamento, get_session, JobLog, Movimentacao, Lote, Produto, Usuario

logger = logging.getLogger(__name__)
 
 
class RelatorioService:
    """
    Orquestra a geração de XLSX e o envio por Gmail.
    Usado por T-11 (sob demanda) e pelo scheduler (agendamento).
    """
 
    # ── Geração + envio sob demanda (RF-20) ───────────────────────────────
 
    @staticmethod
    def gerar_e_enviar_movimentacao(data_ini: date, data_fim: date) -> Path:
        """RF-15: gera relatório de movimentação e envia por e-mail."""
        
 
        caminho = XlsxBuilder.movimentacao(data_ini, data_fim)
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
    def gerar_e_enviar_estoque_atual() -> Path:
        """RF-16: gera relatório de estoque atual e envia por e-mail."""
 
        caminho = XlsxBuilder.estoque_atual()
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
    def gerar_e_enviar_a_vencer(dias: int = 30) -> Path:
        """RF-17: gera relatório de produtos a vencer e envia por e-mail."""
 
        caminho = XlsxBuilder.a_vencer(dias)
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
    def gerar_e_enviar_lotes_vencidos() -> Path:
        """RF-22: gera relatório de lotes vencidos e envia por e-mail."""
 
        caminho = XlsxBuilder.lotes_vencidos()
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

    #── Busca de dados para exibição na UI ───────────────────────────────────────────────
    def buscar_dados_movimentacao(data_ini: date, data_fim: date) -> list[list]:
        """Retorna os dados puros de movimentação para a tabela visual da UI."""

        inicio = dt.combine(data_ini, dt.min.time())
        fim    = dt.combine(data_fim, dt.max.time())

        with get_read_session() as s:
            movs = (
                s.query(Movimentacao)
                .join(Lote).join(Produto).join(Usuario)
                .options(
                    joinedload(Movimentacao.lote).joinedload(Lote.produto),
                    joinedload(Movimentacao.usuario),
                )
                .filter(Movimentacao.data_hora.between(inicio, fim))
                .order_by(Movimentacao.data_hora.desc())
                .all()
            )
            return [
                [
                    m.data_hora.strftime("%d/%m/%Y %H:%M"),
                    m.lote.produto.nome,
                    m.lote.num_lote,
                    m.numero_nf or m.lote.nota_fiscal or "—",
                    m.tipo.value.replace("_", " ").title(),
                    m.quantidade,
                    m.usuario.nome,
                    m.observacao or ""
                ] for m in movs
            ]
    @staticmethod
    def buscar_dados_estoque_atual() -> list[list]:
        """Retorna a posição do estoque para exibição na UI."""

        hoje = date.today()
        with get_read_session() as s:
            lotes = (
                s.query(Lote).join(Produto)
                .options(joinedload(Lote.produto))
                .filter(Produto.ativo == True, Lote.quantidade_atual > 0)
                .order_by(Produto.nome, Lote.data_vencimento)
                .all()
            )
            dados = []
            for l in lotes:
                vencido = False if l.data_vencimento is None else l.data_vencimento < hoje
                diff = None if l.data_vencimento is None else (l.data_vencimento - hoje).days
                
                if diff is None: sit = "Normal"
                elif vencido: sit = "VENCIDO"
                elif diff <= 15: sit = f"Vence em {diff}d"
                else: sit = "Normal"

                dados.append([
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.num_lote,
                    l.nota_fiscal or "—",
                    l.data_fabricacao.strftime("%d/%m/%Y") if l.data_fabricacao else "—",
                    l.data_vencimento.strftime("%d/%m/%Y") if l.data_vencimento else "—",
                    l.quantidade_inicial,
                    l.quantidade_atual,
                    f"R$ {float(l.valor_unitario):,.2f}",
                    f"R$ {float(l.valor_total):,.2f}",
                    sit
                ])
            return dados

    @staticmethod
    def buscar_dados_a_vencer(dias: int = 30) -> list[list]:
        """Retorna produtos próximos ao vencimento para a UI."""

        hoje = date.today()
        limite = hoje + timedelta(days=dias)
        with get_read_session() as s:
            lotes = (
                s.query(Lote).join(Produto)
                .options(joinedload(Lote.produto))
                .filter(
                    Produto.ativo == True, Lote.quantidade_atual > 0,
                    Lote.data_vencimento >= hoje, Lote.data_vencimento <= limite,
                    Lote.data_vencimento.isnot(None),
                )
                .order_by(Lote.data_vencimento).all()
            )
            return [
                [
                    l.produto.nome,
                    l.centro_alocacao.value.capitalize(),
                    l.num_lote,
                    l.nota_fiscal or "—",
                    l.data_vencimento.strftime("%d/%m/%Y"),
                    f"{(l.data_vencimento - hoje).days} dias",
                    l.quantidade_atual,
                    "Crítico" if (l.data_vencimento - hoje).days <= 2 else "Urgente"
                ] for l in lotes
            ]

    @staticmethod
    def buscar_dados_lotes_vencidos() -> list[list]:
        """Retorna os lotes vencidos para a UI."""

        hoje = date.today()
        with get_read_session() as s:
            lotes = (
                s.query(Lote).join(Produto)
                .options(joinedload(Lote.produto))
                .filter(
                    Produto.ativo == True, Lote.quantidade_atual > 0,
                    Lote.data_vencimento < hoje, Lote.data_vencimento.isnot(None),
                )
                .order_by(Lote.data_vencimento).all()
            )
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
            Sistema de Controle de Estoque — Centro de Uronefrologia<br>
            Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}
          </p>
        </div>
      </div>
    </body></html>
    """