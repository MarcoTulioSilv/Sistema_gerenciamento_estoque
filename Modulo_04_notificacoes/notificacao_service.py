"""
Modulo_04_notificacoes · notificacao_service.py
Sprint 5 — NotificacaoService: alertas automáticos de vencimento e estoque baixo.

Responsabilidades:
  - Verificar lotes próximos ao vencimento (30d, 15d, 7d) e vencidos.
  - Controlar duplicidade via notificacao_log (mesmo lote + marco + dia).
  - Disparar alerta imediato de estoque baixo após retirada (RF-13).
  - Registrar sucesso/falha em notificacao_log e job_log.

Chamado por:
  - Scheduler (job diário) → verificar_vencimentos() e alertar_lotes_vencidos()
  - EstoqueService.registrar_retirada() → alertar_estoque_baixo()
"""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from Modulo_06_dados import (
    get_session, get_read_session,
    Lote, Produto, NotificacaoLog, JobLog,
    TipoAlertaEnum,
)
from Modulo_04_notificacoes.gmail_client import GmailClient
from Modulo_04_notificacoes.job_log_repo import JobLogRepo

logger = logging.getLogger(__name__)


class NotificacaoService:
    """
    Serviço de notificações por e-mail (RF-10, RF-11, RF-12, RF-13, RF-22).
    Todos os métodos são estáticos — sem estado entre chamadas.
    """

    # ── Marcos de vencimento e seus ENUMs ────────────────────────────────────
    _MARCOS: list[tuple[int, TipoAlertaEnum]] = [
        (7,  TipoAlertaEnum.vencimento_7),
        (15,  TipoAlertaEnum.vencimento_15),
        (30, TipoAlertaEnum.vencimento_30),
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def verificar_vencimentos() -> dict:
        """
        RF-10, RF-11, RF-12 — Verifica todos os lotes ativos e dispara e-mails
        para os marcos de 30d, 15d e 7d. Controla duplicidade via notificacao_log.

        Retorna resumo: {"enviados": int, "ignorados": int, "erros": int}
        """
        hoje = date.today()
        resumo = {"enviados": 0, "ignorados": 0, "erros": 0}

        try:
            with get_read_session() as s:
                lotes = (
                    s.query(Lote)
                    .join(Produto)
                    .filter(
                        Lote.quantidade_atual > 0,
                        Lote.data_vencimento >= hoje,
                        Produto.ativo == True,
                        Lote.data_vencimento.isnot(None)
                    )
                    .all()
                )
                # Materializar para uso fora da sessão
                dados_lotes = [
                    {
                        "id":              l.id,
                        "num_lote":        l.num_lote,
                        "data_vencimento": l.data_vencimento,
                        "produto_nome":    l.produto.nome,
                        "quantidade":      l.quantidade_atual,
                    }
                    for l in lotes
                ]
        except Exception as exc:
            logger.error("Erro ao consultar lotes para verificação de vencimento: %s", exc)
            NotificacaoService._registrar_job_log(
                "verificar_vencimentos", sucesso=False, detalhe=str(exc))
            return resumo

        for dados in dados_lotes:
            dias_restantes = (dados["data_vencimento"] - hoje).days
            for dias_marco, tipo_alerta in NotificacaoService._MARCOS:
                if dias_restantes > dias_marco:
                    continue
                # Verifica duplicidade: já enviou este marco hoje para este lote?
                if NotificacaoService._ja_enviado_hoje(dados["id"], tipo_alerta):
                    resumo["ignorados"] += 1
                    continue
                # Dispara e-mail
                ok, erro = NotificacaoService._enviar_alerta_vencimento(
                    dados, dias_marco, tipo_alerta)
                NotificacaoService._registrar_notificacao(
                    dados["id"], tipo_alerta, sucesso=ok, erro_msg=erro)
                if ok:
                    resumo["enviados"] += 1
                else:
                    resumo["erros"] += 1
                break   # Apenas o marco mais urgente por execução (7d tem prioridade sobre 15d)

        logger.info("verificar_vencimentos: %s", resumo)
        NotificacaoService._registrar_job_log(
            "verificar_vencimentos", sucesso=True,
            detalhe=f"enviados={resumo['enviados']} erros={resumo['erros']}")
        return resumo

    @staticmethod
    def alertar_lotes_vencidos() -> dict:
        """
        RF-22 — Envia e-mail diário consolidado com todos os lotes vencidos em estoque.
        Só envia se existirem lotes vencidos.

        Retorna resumo: {"lotes_vencidos": int, "enviado": bool}
        """
        hoje = date.today()
        resumo = {"lotes_vencidos": 0, "enviado": False}

        try:
            with get_read_session() as s:
                lotes = (
                    s.query(Lote)
                    .join(Produto)
                    .filter(
                        Lote.quantidade_atual > 0,
                        Lote.data_vencimento < hoje,
                        Produto.ativo == True,
                        Lote.data_vencimento.isnot(None)
                    )
                    .order_by(Lote.data_vencimento.asc())
                    .all()
                )
                dados_lotes = [
                    {
                        "produto_nome":    l.produto.nome,
                        "num_lote":        l.num_lote,
                        "data_vencimento": l.data_vencimento,
                        "quantidade":      l.quantidade_atual,
                        "id":              l.id,
                    }
                    for l in lotes
                ]
        except Exception as exc:
            logger.error("Erro ao consultar lotes vencidos: %s", exc)
            NotificacaoService._registrar_job_log(
                "alertar_lotes_vencidos", sucesso=False, detalhe=str(exc))
            return resumo

        resumo["lotes_vencidos"] = len(dados_lotes)
        if resumo["lotes_vencidos"] == 0:
            logger.info("alertar_lotes_vencidos: nenhum lote vencido em estoque.")
            NotificacaoService._registrar_job_log(
                "alertar_lotes_vencidos", sucesso=True,
                detalhe="Nenhum lote vencido.")
            
            return resumo

        # Verifica duplicidade: já enviou alerta de 'vencido' hoje?
        # Usa lote_id do primeiro lote como referência (controle por dia, não por lote)
        if resumo["lotes_vencidos"] > 0:
            tipo = TipoAlertaEnum.vencido
            ok, erro = NotificacaoService._enviar_consolidado_vencidos(dados_lotes)
        # Registra um log por lote
        for d in dados_lotes:
            NotificacaoService._registrar_notificacao(
                d["id"], tipo, sucesso=ok, erro_msg=erro)

        resumo["enviado"] = ok
        logger.info("alertar_lotes_vencidos: %d lote(s), enviado=%s", len(dados_lotes), ok)
        NotificacaoService._registrar_job_log(
            "alertar_lotes_vencidos", sucesso=ok,
            detalhe=f"lotes={len(dados_lotes)} enviado={ok}" + (f" erro={erro}" if erro else ""))
        return resumo

    @staticmethod
    def alertar_estoque_baixo(produto_id: int) -> bool:
        """
        RF-13, RN-03 — Dispara alerta imediato de estoque baixo após retirada.
        Chamado por EstoqueService.registrar_retirada() quando retorna True.

        Retorna True se o e-mail foi enviado com sucesso.
        """
        try:
            with get_read_session() as s:
                produto = s.get(Produto, produto_id)
                if produto is None:
                    logger.warning("alertar_estoque_baixo: produto %s não encontrado.", produto_id)
                    return False
                saldo = sum(
                    l.quantidade_atual for l in produto.lotes
                    if l.quantidade_atual > 0
                )
                dados = {
                    "produto_nome":    produto.nome,
                    "estoque_minimo":  produto.estoque_minimo,
                    "saldo_atual":     saldo,
                }
        except Exception as exc:
            logger.error("Erro ao consultar produto %s para alerta: %s", produto_id, exc)
            return False

        ok, erro = NotificacaoService._enviar_alerta_estoque_baixo(dados)

        # Registra em notificacao_log usando lote mais antigo com saldo como referência
        try:
            with get_read_session() as s:
                lote_ref = (
                    s.query(Lote)
                    .filter(
                        Lote.produto_id == produto_id,
                        Lote.quantidade_atual > 0,
                    )
                    .order_by(Lote.data_vencimento.asc())
                    .first()
                )
                if lote_ref:
                    NotificacaoService._registrar_notificacao(
                        lote_ref.id, TipoAlertaEnum.estoque_baixo,
                        sucesso=ok, erro_msg=erro)
        except Exception as exc:
            logger.error("Erro ao registrar log de estoque baixo: %s", exc)

        return ok

    # ─────────────────────────────────────────────────────────────────────────
    # Controle de duplicidade
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _ja_enviado_hoje(lote_id: int, tipo_alerta: TipoAlertaEnum) -> bool:
        """
        Verifica se já existe registro em notificacao_log para este lote,
        este tipo de alerta e o dia atual (RN-02 — sem duplicatas no mesmo dia).
        """
        hoje_inicio = datetime.combine(date.today(), datetime.min.time())
        try:
            with get_read_session() as s:
                existe = (
                    s.query(func.count(NotificacaoLog.id))
                    .filter(
                        NotificacaoLog.lote_id     == lote_id,
                        NotificacaoLog.tipo_alerta == tipo_alerta,
                        NotificacaoLog.enviado_em  >= hoje_inicio,
                        NotificacaoLog.sucesso     == True,
                    )
                    .scalar()
                )
                return (existe or 0) > 0
        except Exception as exc:
            logger.error("Erro ao verificar duplicidade de notificação: %s", exc)
            return False   # Em caso de erro, permite o envio (preferência segura)

    # ─────────────────────────────────────────────────────────────────────────
    # Montagem e envio de e-mails
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _enviar_alerta_vencimento(
        dados: dict, dias_marco: int
    ) -> tuple[bool, str | None]:
        """Monta e envia e-mail de alerta de vencimento próximo."""
        venc_str = dados["data_vencimento"].strftime("%d/%m/%Y")
        assunto = (
            f"SCE ⚠ Alerta de vencimento — {dados['produto_nome']} "
            f"(lote {dados['num_lote']}) vence em {dias_marco} dia(s)"
        )
        corpo = _html_alerta_vencimento(
            produto_nome    = dados["produto_nome"],
            num_lote        = dados["num_lote"],
            data_vencimento = venc_str,
            dias_restantes  = dias_marco,
            quantidade      = dados["quantidade"],
        )
        try:
            GmailClient.enviar(assunto=assunto, corpo_html=corpo)
            logger.info("Alerta de vencimento enviado: lote %s marco %sd", dados["id"], dias_marco)
            return True, None
        except Exception as exc:
            logger.error("Falha ao enviar alerta vencimento lote %s: %s", dados["id"], exc)
            return False, str(exc)[:255]

    @staticmethod
    def _enviar_consolidado_vencidos(dados_lotes: list[dict]) -> tuple[bool, str | None]:
        """Monta e envia e-mail consolidado com todos os lotes vencidos."""
        assunto = f"SCE 🔴 {len(dados_lotes)} lote(s) VENCIDO(S) em estoque — {date.today().strftime('%d/%m/%Y')}"
        corpo = _html_consolidado_vencidos(dados_lotes)
        try:
            GmailClient.enviar(assunto=assunto, corpo_html=corpo)
            logger.info("Alerta consolidado de vencidos enviado: %d lote(s).", len(dados_lotes))
            return True, None
        except Exception as exc:
            logger.error("Falha ao enviar alerta consolidado de vencidos: %s", exc)
            return False, str(exc)[:255]

    @staticmethod
    def _enviar_alerta_estoque_baixo(dados: dict) -> tuple[bool, str | None]:
        """Monta e envia e-mail de alerta de estoque baixo."""
        assunto = f"SCE ⚠ Estoque baixo — {dados['produto_nome']}"
        corpo = _html_estoque_baixo(
            produto_nome   = dados["produto_nome"],
            saldo_atual    = dados["saldo_atual"],
            estoque_minimo = dados["estoque_minimo"],
        )
        try:
            GmailClient.enviar(assunto=assunto, corpo_html=corpo)
            logger.info("Alerta de estoque baixo enviado: %s", dados["produto_nome"])
            return True, None
        except Exception as exc:
            logger.error("Falha ao enviar alerta de estoque baixo: %s", exc)
            return False, str(exc)[:255]

    # ─────────────────────────────────────────────────────────────────────────
    # Persistência em log
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _registrar_notificacao(
        lote_id: int,
        tipo_alerta: TipoAlertaEnum,
        sucesso: bool,
        erro_msg: str | None = None,
    ) -> None:
        """Insere registro em notificacao_log."""
        try:
            with get_session() as s:
                s.add(NotificacaoLog(
                    lote_id     = lote_id,
                    tipo_alerta = tipo_alerta,
                    enviado_em  = datetime.utcnow(),
                    sucesso     = sucesso,
                    erro_msg    = erro_msg,
                ))
        except Exception as exc:
            logger.error("Erro ao registrar notificacao_log: %s", exc)

    @staticmethod
    def _registrar_job_log(
        job_nome: str, sucesso: bool, detalhe: str | None = None
    ) -> None:
        """Insere registro em job_log (rastreabilidade do scheduler)."""
        try:
            with get_session() as s:
                s.add(JobLog(
                    job_nome     = job_nome,
                    executado_em = datetime.utcnow(),
                    sucesso      = sucesso,
                    detalhe      = (detalhe or "")[:255],
                ))
        except Exception as exc:
            logger.error("Erro ao registrar job_log: %s", exc)

    #__________ Leitura para telas (T-18/T-19) ___________________________________________
    @staticmethod
    def listar_notificacoes_no_periodo(inicio: datetime, fim: datetime, limite: int = 200) -> list[NotificacaoLog]:
        with get_read_session() as s:
            itens = (s.query(NotificacaoLog)
                     .options(joinedload(NotificacaoLog.lote).joinedload(Lote.produto))
                     .filter(NotificacaoLog.enviado_em.between(inicio, fim))
                     .order_by(NotificacaoLog.enviado_em.desc())
                     .limit(limite)
                     .all())
            s.expunge_all()
            return itens

    @staticmethod
    def listar_job_logs_no_periodo(inicio: datetime, fim: datetime, limite: int = 100) -> list[JobLog]:
        return JobLogRepo.listar_no_periodo(inicio, fim, limite)

    @staticmethod
    def listar_job_logs_por_nome(job_nome: str, limite: int = 10) -> list[JobLog]:
        return JobLogRepo.listar_por_job(job_nome, limite)


# ─────────────────────────────────────────────────────────────────────────────
# Templates HTML dos e-mails
# ─────────────────────────────────────────────────────────────────────────────

_HTML_BASE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8">
<style>
  body  {{ font-family: Arial, sans-serif; background:#F2F1ED; margin:0; padding:20px; }}
  .card {{ background:#ffffff; border-radius:8px; padding:24px 28px;
           max-width:560px; margin:0 auto; border:1px solid #E8E6DE; }}
  .hdr  {{ background:{cor_hdr}; color:#fff; border-radius:6px;
           padding:14px 20px; margin-bottom:20px; }}
  .hdr h2 {{ margin:0; font-size:16px; }}
  .hdr p  {{ margin:4px 0 0; font-size:12px; opacity:.85; }}
  table {{ width:100%; border-collapse:collapse; margin:14px 0; }}
  th    {{ background:#F2F1ED; text-align:left; padding:7px 10px;
           font-size:11px; color:#5F5E5A; text-transform:uppercase; }}
  td    {{ padding:7px 10px; font-size:13px; color:#3d3d3a;
           border-bottom:1px solid #F5F4F0; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:10px;
            font-size:11px; font-weight:bold; }}
  .rodape {{ font-size:11px; color:#888780; margin-top:20px; text-align:center; }}
</style>
</head>
<body><div class="card">{conteudo}</div></body>
</html>
"""


def _html_alerta_vencimento(
    produto_nome: str,
    num_lote: str,
    data_vencimento: str,
    dias_restantes: int,
    quantidade: int,
) -> str:
    cor_hdr = "#A32D2D" if dias_restantes <= 2 else "#BA7517"
    badge_cor = "#FCEBEB" if dias_restantes <= 2 else "#FAEEDA"
    badge_txt = "#A32D2D" if dias_restantes <= 2 else "#854F0B"

    conteudo = f"""
    <div class="hdr" style="background:{cor_hdr}">
      <h2>⚠ Alerta de Vencimento</h2>
      <p>SCE — Sistema de Controle de Estoque</p>
    </div>
    <p>O lote abaixo está próximo do vencimento e requer atenção:</p>
    <table>
      <tr><th>Produto</th><td><strong>{produto_nome}</strong></td></tr>
      <tr><th>Nº do lote</th><td>{num_lote}</td></tr>
      <tr><th>Vencimento</th><td>{data_vencimento}</td></tr>
      <tr><th>Dias restantes</th>
          <td><span class="badge" style="background:{badge_cor};color:{badge_txt}">
            {dias_restantes} dia(s)
          </span></td></tr>
      <tr><th>Quantidade em estoque</th><td>{quantidade} unidade(s)</td></tr>
    </table>
    <p>Providencie a utilização ou descarte conforme protocolo.</p>
    <p class="rodape">E-mail automático gerado pelo SCE em {date.today().strftime('%d/%m/%Y')}.</p>
    """
    return _HTML_BASE.format(cor_hdr=cor_hdr, conteudo=conteudo)


def _html_consolidado_vencidos(dados_lotes: list[dict]) -> str:
    linhas = "".join(
        f"<tr>"
        f"<td>{d['produto_nome']}</td>"
        f"<td>{d['num_lote']}</td>"
        f"<td>{d['data_vencimento'].strftime('%d/%m/%Y')}</td>"
        f"<td>{(date.today() - d['data_vencimento']).days}d</td>"
        f"<td>{d['quantidade']}</td>"
        f"</tr>"
        for d in dados_lotes
    )
    conteudo = f"""
    <div class="hdr" style="background:#A32D2D">
      <h2>🔴 Lotes Vencidos em Estoque</h2>
      <p>SCE — Sistema de Controle de Estoque · {date.today().strftime('%d/%m/%Y')}</p>
    </div>
    <p><strong>{len(dados_lotes)} lote(s) com data de vencimento ultrapassada</strong>
       ainda possuem saldo em estoque. Ação imediata necessária.</p>
    <table>
      <tr>
        <th>Produto</th><th>Lote</th><th>Vencimento</th>
        <th>Há quanto tempo</th><th>Qtd</th>
      </tr>
      {linhas}
    </table>
    <p>Proceda com a baixa ou descarte conforme protocolo da clínica.</p>
    <p class="rodape">E-mail automático gerado pelo SCE. Verifique o dashboard T-22 para detalhes.</p>
    """
    return _HTML_BASE.format(cor_hdr="#A32D2D", conteudo=conteudo)


def _html_estoque_baixo(
    produto_nome: str, saldo_atual: int, estoque_minimo: int
) -> str:
    conteudo = f"""
    <div class="hdr" style="background:#BA7517">
      <h2>⚠ Estoque Baixo</h2>
      <p>SCE — Sistema de Controle de Estoque</p>
    </div>
    <p>O produto abaixo atingiu ou ficou abaixo do estoque mínimo configurado:</p>
    <table>
      <tr><th>Produto</th><td><strong>{produto_nome}</strong></td></tr>
      <tr><th>Saldo atual</th>
          <td><span class="badge" style="background:#FAEEDA;color:#854F0B">
            {saldo_atual} unidade(s)
          </span></td></tr>
      <tr><th>Estoque mínimo</th><td>{estoque_minimo} unidade(s)</td></tr>
    </table>
    <p>Providencie a reposição do estoque.</p>
    <p class="rodape">E-mail automático gerado pelo SCE em {date.today().strftime('%d/%m/%Y')}.</p>
    """
    return _HTML_BASE.format(cor_hdr="#BA7517", conteudo=conteudo)