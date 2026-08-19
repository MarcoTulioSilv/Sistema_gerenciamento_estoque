"""
MOD-07 · Modulo_07_patrimonio · coleta_web_service.py

Camada de apresentação HTTP do ColetaWebService (AD-14) — processo headless
que atende dispositivos móveis na rede interna: consulta pública de bem por
QR (RF-37) e registro de leitura em sessão de inventário pareada (RF-36).

REGRA ARQUITETURAL (DAS v1.5 §2.3): este módulo é só camada de apresentação.
Toda decisão de negócio vem de InventarioService/PatrimonioService — nunca
repositório, nunca regra própria aqui.

CONTRATO DE URL — gravado em toda etiqueta já impressa, não pode mudar sem
invalidar o parque inteiro (R-08):
    GET /p?t=<tombo>          — etiqueta.montar_payload()
    GET /parear?token=<token> — InventarioService.parear_dispositivo()

A MESMA rota /p serve dois propósitos, decidido pela presença de um cookie
de pareamento válido (AD-16): sem cookie válido → consulta pública somente
leitura (RF-37), sem nunca expor por que o cookie falhou (RE-15 — a consulta
nunca deve "parecer quebrada"); com cookie válido → registra a leitura na
sessão pareada num único GET (DAS §5.5) — a câmera nativa do celular abre a
URL da etiqueta e o registro já acontece, sem clique extra.
"""
from __future__ import annotations

import logging

from flask import Flask, Response, request
from markupsafe import escape

from Modulo_05_admin import ConfigService
from Modulo_07_patrimonio.dto import ResultadoLeitura, BemPublico, ContextoColeta
from Modulo_07_patrimonio.excecoes import (
    BemNaoEncontradoError,
    TokenInvalidoError, TokenRevogadoError, TokenExpiradoError,
    SessaoNaoAbertaError, SessaoNaoEncontradaError,
)
from Modulo_07_patrimonio.inventario_service import InventarioService
from Modulo_07_patrimonio.patrimonio_service import PatrimonioService

logger = logging.getLogger(__name__)

_COOKIE_NOME = "sce_coleta_token"
_LIMITE_TOMBO = 64
_LIMITE_TOKEN = 200
_HORAS_TOKEN_PADRAO = 12

_ERROS_PAREAMENTO = (TokenInvalidoError, TokenRevogadoError, TokenExpiradoError, SessaoNaoAbertaError)

_COR_SEVERIDADE = {
    "ok": "#1D9E75",
    "atencao": "#BA7517",
    "erro": "#A32D2D",
}
_BG_SEVERIDADE = {
    "ok": "#EAF3DE",
    "atencao": "#FAEEDA",
    "erro": "#FCEBEB",
}


def criar_app() -> Flask:
    """
    Application factory. Não guarda estado entre requisições — cada rota
    abre sua própria sessão de banco via InventarioService/PatrimonioService
    (que já usam get_session()/get_read_session() por chamada), seguro sob
    as threads de worker do Waitress.
    """
    app = Flask(__name__)
    inventario = InventarioService()
    patrimonio = PatrimonioService()

    @app.get("/p")
    def consultar_ou_registrar():
        tombo = (request.args.get("t") or "").strip()
        if not tombo or len(tombo) > _LIMITE_TOMBO:
            return _pagina_erro("Código inválido", "O código lido não é válido.", 400)

        contexto = _resolver_contexto_pareado(inventario)

        if contexto is not None:
            try:
                resultado = inventario.registrar_leitura(tombo, contexto)
                return _pagina_resultado(resultado)
            except (SessaoNaoAbertaError, SessaoNaoEncontradaError) as exc:
                # Corrida rara: sessão fechou entre resolver_token e
                # registrar_leitura. Cai para consulta pública em vez de
                # mostrar erro — RE-15, a leitura nunca deve "quebrar" pro
                # técnico em campo, só perde o registro (fica no log).
                logger.warning("Sessão indisponível durante leitura pareada (tombo=%s): %s", tombo, exc)

        try:
            bem = patrimonio.consultar_publico(tombo)
        except BemNaoEncontradoError:
            return _pagina_erro("Bem não encontrado", "Nenhum bem foi encontrado para este código.", 404)
        return _pagina_consulta(bem)

    @app.get("/parear")
    def parear():
        token = (request.args.get("token") or "").strip()
        if not token or len(token) > _LIMITE_TOKEN:
            return _pagina_erro("Código inválido", "O código de pareamento não é válido.", 400)

        try:
            contexto = inventario.resolver_token(token)
        except _ERROS_PAREAMENTO as exc:
            return _pagina_erro("Pareamento não realizado", str(exc), 200)

        horas = float(ConfigService.get("coleta_token_horas") or _HORAS_TOKEN_PADRAO)
        resp = Response(_pagina_pareamento_ok(contexto))
        resp.set_cookie(
            _COOKIE_NOME, token, max_age=int(horas * 3600),
            httponly=True, samesite="Lax", secure=False, path="/",
        )
        return resp

    @app.errorhandler(Exception)
    def erro_generico(exc):
        logger.error("Erro não tratado no ColetaWebService: %s", exc, exc_info=True)
        return _pagina_erro("Serviço indisponível", "Ocorreu um erro. Tente novamente em instantes.", 500)

    return app


def _resolver_contexto_pareado(inventario: InventarioService) -> ContextoColeta | None:
    token = request.cookies.get(_COOKIE_NOME)
    if not token:
        return None
    try:
        return inventario.resolver_token(token)
    except _ERROS_PAREAMENTO:
        # Cookie presente mas inválido/expirado/revogado/sessão fechada:
        # tratado exatamente como "sem cookie" — nunca revela o motivo a
        # quem só está consultando a etiqueta (RE-15).
        return None


# ─── Renderização (HTML inline — ver justificativa no plano/CLAUDE.md) ──────

def _layout(titulo: str, corpo: str) -> str:
    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)} — SCE Patrimônio</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
          background: #F2F1ED; color: #3d3d3a; }}
  .topo {{ background: #1F5F5B; color: #fff; padding: 16px 20px; font-weight: bold; }}
  .cartao {{ margin: 16px; background: #fff; border-radius: 10px; padding: 20px;
             box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .linha {{ display: flex; justify-content: space-between; padding: 8px 0;
            border-bottom: 1px solid #E8E6DE; font-size: 15px; }}
  .linha:last-child {{ border-bottom: none; }}
  .rotulo {{ color: #888780; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px;
            font-size: 13px; font-weight: bold; }}
  .titulo-cartao {{ font-size: 18px; font-weight: bold; margin: 0 0 12px; color: #1F5F5B; }}
  .barra-fundo {{ background: #E8E6DE; border-radius: 6px; height: 10px; overflow: hidden; margin-top: 10px; }}
  .barra-preenchida {{ background: #2E8A83; height: 100%; }}
</style>
</head>
<body>
<div class="topo">Centro de Uronefrologia — Patrimônio</div>
{corpo}
</body>
</html>"""


def _pagina_consulta(bem: BemPublico) -> str:
    situacao_label = {"ativo": "Ativo", "em_apuracao": "Em apuração", "baixado": "Baixado"}.get(
        bem.situacao, bem.situacao)
    cor_situacao = "#A32D2D" if bem.baixado else "#27500A"
    bg_situacao = "#FCEBEB" if bem.baixado else "#EAF3DE"
    ultima_manut = bem.ultima_manutencao.strftime("%d/%m/%Y") if bem.ultima_manutencao else "Sem manutenção registrada"

    corpo = f"""
<div class="cartao">
  <p class="titulo-cartao">{escape(bem.tombo)}</p>
  <div class="linha"><span class="rotulo">Descrição</span><span>{escape(bem.descricao)}</span></div>
  <div class="linha"><span class="rotulo">Marca/modelo</span><span>{escape(bem.marca_modelo or "—")}</span></div>
  <div class="linha"><span class="rotulo">Localização</span><span>{escape(bem.localizacao)}</span></div>
  <div class="linha"><span class="rotulo">Situação</span>
    <span class="badge" style="background:{bg_situacao};color:{cor_situacao}">{escape(situacao_label)}</span>
  </div>
  <div class="linha"><span class="rotulo">Última manutenção</span><span>{escape(ultima_manut)}</span></div>
</div>
"""
    return _layout("Consulta de bem", corpo)


def _pagina_resultado(resultado: ResultadoLeitura) -> str:
    cor = _COR_SEVERIDADE.get(resultado.severidade.value, "#3d3d3a")
    bg = _BG_SEVERIDADE.get(resultado.severidade.value, "#F1EFE8")
    progresso_pct = int(resultado.progresso * 100)

    linhas_extra = ""
    if resultado.localizacao_esperada:
        linhas_extra += (f'<div class="linha"><span class="rotulo">Esperado em</span>'
                         f'<span>{escape(resultado.localizacao_esperada)}</span></div>')
    if resultado.localizacao_lida:
        linhas_extra += (f'<div class="linha"><span class="rotulo">Lido em</span>'
                         f'<span>{escape(resultado.localizacao_lida)}</span></div>')

    corpo = f"""
<div class="cartao" style="background:{bg}">
  <p class="titulo-cartao" style="color:{cor}">{escape(resultado.mensagem)}</p>
  {f'<div class="linha"><span class="rotulo">Tombo</span><span>{escape(resultado.tombo)}</span></div>' if resultado.tombo else ""}
  {f'<div class="linha"><span class="rotulo">Descrição</span><span>{escape(resultado.descricao_bem)}</span></div>' if resultado.descricao_bem else ""}
  {linhas_extra}
</div>
<div class="cartao">
  <div class="linha"><span class="rotulo">Progresso da sessão</span>
    <span>{resultado.total_conferido}/{resultado.total_esperado}</span></div>
  <div class="barra-fundo"><div class="barra-preenchida" style="width:{progresso_pct}%"></div></div>
</div>
"""
    return _layout("Leitura registrada", corpo)


def _pagina_pareamento_ok(contexto: ContextoColeta) -> str:
    dispositivo = f" ({escape(contexto.dispositivo_label)})" if contexto.dispositivo_label else ""
    corpo = f"""
<div class="cartao" style="background:#EAF3DE">
  <p class="titulo-cartao" style="color:#27500A">Dispositivo pareado{dispositivo}</p>
  <p>Agora é só ler a etiqueta de cada bem com a câmera do celular — a leitura
  é registrada automaticamente na sessão de inventário.</p>
</div>
"""
    return _layout("Pareamento confirmado", corpo)


def _pagina_erro(titulo: str, mensagem: str, status: int) -> tuple[str, int]:
    corpo = f"""
<div class="cartao" style="background:#FCEBEB">
  <p class="titulo-cartao" style="color:#A32D2D">{escape(titulo)}</p>
  <p>{escape(mensagem)}</p>
</div>
"""
    return _layout(titulo, corpo), status
