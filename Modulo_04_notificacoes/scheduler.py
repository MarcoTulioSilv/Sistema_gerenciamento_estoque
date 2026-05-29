"""
Modulo_04_notificacoes · scheduler.py
Sprint 5 — Scheduler APScheduler: job diário de notificações.

Design (conforme DAS 5.2):
  - BackgroundScheduler in-process, sem daemon externo.
  - Um único job diário 'notificacoes_diarias' que executa:
      1. verificar_vencimentos()   (RF-10, RF-11, RF-12)
      2. alertar_lotes_vencidos()  (RF-22)
  - Horário configurável via tabela configuracao (chave 'notif_horario').
  - Falha em qualquer alerta individual não interrompe os demais.
  - job_log registra cada execução (sucesso ou falha).

Uso em main.py / app.py:
    from Modulo_04_notificacoes.scheduler import NotificacaoScheduler
    scheduler = NotificacaoScheduler()
    scheduler.iniciar()          # chamado uma vez no startup
    ...
    scheduler.parar()            # chamado no shutdown da aplicação
"""
import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from Modulo_03_relatorios import RelatorioService
from Modulo_04_notificacoes import NotificacaoService
from Modulo_06_dados import get_read_session, Configuracao, RelatorioAgendamento, get_session

logger = logging.getLogger(__name__)

_JOB_ID = "notificacoes_diarias"


class NotificacaoScheduler:
    """
    Encapsula o BackgroundScheduler do APScheduler para o job de notificações.
    Instanciar uma única vez e manter referência viva enquanto o app rodar.
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        self._iniciado = False

    # ── Ciclo de vida ──────────────────────────────────────────────────────

    def iniciar(self):
        if self._scheduler.running:
            return

        # 1. Adiciona o Job diário de Notificações Vitais (lotes vencendo/vencidos)
        h, m = self._ler_horario_configurado()
        self._scheduler.add_job(
            _executar_job_notificacoes,
            CronTrigger(hour=h, minute=m),
            id=_JOB_ID,
            replace_existing=True
        )
        
        # 2. Varre o banco e adiciona os jobs dos Relatórios configurados
        self.atualizar_relatorios_em_tempo_real()

        self._scheduler.start()
        self._iniciado = True
        logger.info("Scheduler iniciado com sucesso.")

    def atualizar_relatorios_em_tempo_real(self):
        """Lê a tabela relatorio_agendamento e cria jobs estritamente nos dias necessários."""
        try:
            from Modulo_06_dados import get_read_session, RelatorioAgendamento
            with get_read_session() as s:
                agendamentos = s.query(RelatorioAgendamento).all()
                
                for ag in agendamentos:
                    job_id = f"relatorio_{ag.tipo_relatorio.value}"
                    
                    # Se está desabilitado, removemos do scheduler. Ele NUNCA vai acordar.
                    if not ag.habilitado:
                        if self._scheduler.get_job(job_id):
                            self._scheduler.remove_job(job_id)
                        continue
                        
                    hora = ag.horario.hour
                    minuto = ag.horario.minute
                    
                    # MÁGICA DA EFICIÊNCIA: Configura o CronTrigger para a periodicidade exata!
                    if ag.periodicidade.value == "diario":
                        # Acorda todo dia no horário marcado
                        trigger = CronTrigger(hour=hora, minute=minuto)
                        
                    elif ag.periodicidade.value == "semanal":
                        # Acorda APENAS nas Segundas-feiras (mon) no horário marcado
                        trigger = CronTrigger(day_of_week='mon', hour=hora, minute=minuto)
                        
                    elif ag.periodicidade.value == "mensal":
                        # Acorda APENAS no dia 1º de cada mês no horário marcado
                        trigger = CronTrigger(day='1', hour=hora, minute=minuto)
                        
                    else:
                        continue

                    # Adiciona ou atualiza o Job no motor do APScheduler
                    self._scheduler.add_job(
                        _executar_job_relatorio,
                        trigger,
                        args=[ag.tipo_relatorio.value],
                        id=job_id,
                        replace_existing=True
                    )
                    
            logger.info("⏰ APScheduler otimizado: Relatórios agendados apenas para os dias úteis.")
        except Exception as exc:
            logger.error(f"Erro ao otimizar agendamentos no scheduler: {exc}")


    def parar(self) -> None:
        """Para o scheduler graciosamente no encerramento da aplicação."""
        if self._iniciado:
            self._scheduler.shutdown(wait=False)
            self._iniciado = False
            logger.info("NotificacaoScheduler encerrado.")

    def reconfigurar_horario(self, hora: int, minuto: int) -> None:
        """
        Atualiza o horário do job sem reiniciar o scheduler.
        Chamado por T-20 (configuração de agendamento — Sprint 6).
        """
        if not self._iniciado:
            return
        self._registrar_job(hora, minuto)
        logger.info(
            "Horário do job de notificações reconfigurado para %02d:%02d.", hora, minuto)

    def executar_agora(self) -> None:
        """
        Executa o job imediatamente (fora do horário agendado).
        Útil para TI testar as notificações via T-20.
        """
        logger.info("Execução manual do job de notificações iniciada.")
        _executar_job_notificacoes()

    # ── Internos ───────────────────────────────────────────────────────────

    def _registrar_job(self, hora: int, minuto: int) -> None:
        """Adiciona ou substitui o job cron no scheduler."""
        self._scheduler.add_job(
            func         = _executar_job_notificacoes,
            trigger      = CronTrigger(hour=hora, minute=minuto),
            id           = _JOB_ID,
            replace_existing = True,
            misfire_grace_time = 3600,   # tolera até 1h de atraso (RN-02)
        )

    @staticmethod
    def _ler_horario_configurado() -> tuple[int, int]:
        """
        Lê 'notif_horario' da tabela configuracao (formato 'HH:MM').
        Retorna (hora, minuto). Padrão: (7, 0).
        """
        try:
            with get_read_session() as s:
                cfg = s.query(Configuracao).filter_by(chave="notif_horario").first()
                if cfg and cfg.valor:
                    partes = cfg.valor.strip().split(":")
                    return int(partes[0]), int(partes[1])
        except Exception as exc:
            logger.warning("Erro ao ler horário de notificações: %s — usando 07:00.", exc)
        return 7, 0


# ── Função executada pelo APScheduler (fora da classe para evitar referência) ──

def _executar_job_notificacoes() -> None:
    """
    Corpo do job diário. Importação local para evitar circular import
    e garantir que o módulo é carregado apenas quando necessário.
    """

    logger.info("=== Job notificações diárias iniciado ===")
    inicio = datetime.utcnow()

    # 1. Alertas de vencimento próximo (15d, 7d, 2d)
    try:
        resumo_venc = NotificacaoService.verificar_vencimentos()
        logger.info("Vencimentos: %s", resumo_venc)
    except Exception as exc:
        logger.error("Erro inesperado em verificar_vencimentos: %s", exc)

    # 2. Alerta consolidado de lotes vencidos (RF-22)
    try:
        resumo_vencidos = NotificacaoService.alertar_lotes_vencidos()
        logger.info("Vencidos: %s", resumo_vencidos)
    except Exception as exc:
        logger.error("Erro inesperado em alertar_lotes_vencidos: %s", exc)

    duracao = (datetime.utcnow() - inicio).total_seconds()
    logger.info("=== Job notificações diárias concluído em %.1fs ===", duracao)

def _executar_job_relatorio(tipo_relatorio_str: str) -> None:
    """Disparado pelo APScheduler APENAS no momento exato em que deve ser enviado."""
    logger.info(f"=== Iniciando job de envio do relatório: {tipo_relatorio_str} ===")
    
    try: 
        with get_session() as s:
            ag = s.query(RelatorioAgendamento).filter_by(tipo_relatorio=tipo_relatorio_str).first()
            
            # Última checagem de segurança 
            if not ag or not ag.habilitado:
                logger.info(f"Relatório {tipo_relatorio_str} foi desabilitado. Abortando envio.")
                return
                
            logger.info(f"Gerando relatório {tipo_relatorio_str}...")
            
            fim = date.today()
            if ag.periodicidade.value == "diario":
                ini = fim - timedelta(days=1)
            elif ag.periodicidade.value == "mensal":
                ini = fim - timedelta(days=30)
            else: # Semanal ou default
                ini = fim - timedelta(days=7)
            try:
                if tipo_relatorio_str == "movimentacao":
                    RelatorioService.gerar_e_enviar_movimentacao(ini, fim)
                elif tipo_relatorio_str == "estoque_atual":   
                    RelatorioService.gerar_e_enviar_estoque_atual()
                elif tipo_relatorio_str == "a_vencer":
                    RelatorioService.gerar_e_enviar_a_vencer()
                elif tipo_relatorio_str == "lotes_vencidos":
                    RelatorioService.gerar_e_enviar_lotes_vencidos()
            except Exception as exc:
                    logger.error("Erro ao gerar relatório '%s': %s", tipo_relatorio_str, exc)
                    logger.info(f"Erro ao gerar relatório '{tipo_relatorio_str}': {exc}")
            
            # Atualiza a data de último envio apenas para auditoria na interface
            ag.ultimo_envio = datetime.now()
            s.commit()
            
            logger.info(f"Relatório {tipo_relatorio_str} enviado com sucesso!")
                
    except Exception as exc:
        logger.error(f"Erro crítico ao processar o relatório {tipo_relatorio_str}: {exc}")