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
    GET  /p?t=<tombo>          — etiqueta.montar_payload()
    GET  /parear?token=<token> — convite fixo da sessão (RF-36 revisado)
    POST /parear                — confirma o cadastro do aparelho

PAREAMENTO EM DUAS FASES (RF-36 revisado — corrige "dispositivo fantasma")
    O QR exibido no desktop (T-26) é um CONVITE fixo por sessão: escaneá-lo
    não cria nada no banco por si só, só valida que a sessão aceita
    pareamento e mostra um formulário. O ColetaToken real (o que aparece em
    "Dispositivos ativos") só nasce quando o celular efetivamente confirma
    o cadastro (POST), com um nome e — se a sessão for de escopo geral —
    uma localização escolhida por ele mesmo.

    Como o navegador não expõe o MAC do aparelho, a identidade entre
    pareamentos é um id aleatório gravado num cookie de longa duração
    (sce_device_id): reabrir o link do convite no mesmo celular reconecta
    ao token existente em vez de duplicar.

A MESMA rota /p serve dois propósitos, decidido pela presença de um cookie
de pareamento válido (AD-16): sem cookie válido → consulta pública somente
leitura (RF-37), sem nunca expor por que o cookie falhou (RE-15 — a consulta
nunca deve "parecer quebrada"); com cookie válido → registra a leitura na
sessão pareada num único GET (DAS §5.5) — a câmera nativa do celular abre a
URL da etiqueta e o registro já acontece, sem clique extra. Essa regra vale
só para /p — /parear e /localizacao sempre mostram o motivo real do erro,
já que ali o usuário está deliberadamente gerenciando o pareamento, não
lendo uma etiqueta de bem.
"""
from __future__ import annotations

import logging
import secrets

from flask import Flask, Response, request
from markupsafe import escape

from Modulo_05_admin import ConfigService
from Modulo_07_patrimonio.dto import ResultadoLeitura, BemPublico, ContextoColeta, ConviteColeta
from Modulo_07_patrimonio.excecoes import (
    BemNaoEncontradoError,
    TokenInvalidoError, TokenRevogadoError, TokenExpiradoError,
    SessaoNaoAbertaError, SessaoNaoEncontradaError, LocalizacaoNaoEncontradaError,
    EscopoFixoError,
)
from Modulo_07_patrimonio.inventario_service import InventarioService
from Modulo_07_patrimonio.patrimonio_service import PatrimonioService

logger = logging.getLogger(__name__)

_COOKIE_NOME = "sce_coleta_token"
_COOKIE_DISPOSITIVO = "sce_device_id"
_DISPOSITIVO_ID_BYTES = 24
_DISPOSITIVO_ID_DIAS = 180
_LIMITE_TOMBO = 64
_LIMITE_TOKEN = 200
_LIMITE_NOME = 60
_HORAS_TOKEN_PADRAO = 12

_ERROS_PAREAMENTO = (TokenInvalidoError, TokenRevogadoError, TokenExpiradoError, SessaoNaoAbertaError)
_ERROS_CONVITE = (TokenInvalidoError, SessaoNaoAbertaError, LocalizacaoNaoEncontradaError)

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

    @app.route("/parear", methods=["GET", "POST"])
    def parear():
        if request.method == "POST":
            return _confirmar_pareamento(inventario)

        token = (request.args.get("token") or "").strip()
        if not token or len(token) > _LIMITE_TOKEN:
            return _pagina_erro("Código inválido", "O código de pareamento não é válido.", 400)

        try:
            convite = inventario.resolver_convite(token)
        except _ERROS_CONVITE as exc:
            return _pagina_erro("Pareamento não realizado", str(exc), 200)

        dispositivo_id = request.cookies.get(_COOKIE_DISPOSITIVO)
        if dispositivo_id:
            existente = inventario.buscar_dispositivo_conhecido(convite.inventario_id, dispositivo_id)
            if existente:
                return _resposta_pareada(existente.token, existente.dispositivo_label)

        return _pagina_cadastro_dispositivo(convite, token)

    @app.route("/localizacao", methods=["GET", "POST"])
    def localizacao():
        contexto = _resolver_contexto_pareado(inventario)
        if contexto is None:
            return _pagina_erro("Não pareado", "Escaneie o QR de pareamento antes de trocar de localização.", 200)

        if request.method == "POST":
            localizacao_id = request.form.get("localizacao_id", type=int)
            if not localizacao_id:
                return _pagina_erro("Dados incompletos", "Selecione uma localização.", 400)
            try:
                inventario.trocar_localizacao(contexto, localizacao_id)
            except EscopoFixoError as exc:
                return _pagina_erro("Não é possível trocar", str(exc), 200)
            except (SessaoNaoAbertaError, LocalizacaoNaoEncontradaError) as exc:
                return _pagina_erro("Não foi possível trocar", str(exc), 200)
            return _pagina_localizacao_trocada()

        try:
            dados = inventario.opcoes_troca_localizacao(contexto)
        except SessaoNaoAbertaError as exc:
            return _pagina_erro("Sessão encerrada", str(exc), 200)
        return _pagina_trocar_localizacao(dados, contexto.localizacao_id)

    @app.errorhandler(Exception)
    def erro_generico(exc):
        logger.error("Erro não tratado no ColetaWebService: %s", exc, exc_info=True)
        return _pagina_erro("Serviço indisponível", "Ocorreu um erro. Tente novamente em instantes.", 500)

    return app


def _confirmar_pareamento(inventario: InventarioService):
    convite_token = (request.form.get("token") or "").strip()
    nome = (request.form.get("nome") or "").strip()[:_LIMITE_NOME] or None
    localizacao_id = request.form.get("localizacao_id", type=int)

    if not convite_token or len(convite_token) > _LIMITE_TOKEN:
        return _pagina_erro("Código inválido", "O código de pareamento não é válido.", 400)

    dispositivo_id = request.cookies.get(_COOKIE_DISPOSITIVO) or secrets.token_urlsafe(_DISPOSITIVO_ID_BYTES)

    try:
        device_token = inventario.registrar_dispositivo(convite_token, localizacao_id, nome, dispositivo_id)
    except _ERROS_CONVITE as exc:
        return _pagina_erro("Pareamento não realizado", str(exc), 200)

    return _resposta_pareada(device_token, nome, dispositivo_id=dispositivo_id)


def _resposta_pareada(device_token: str, dispositivo_label: str | None, dispositivo_id: str | None = None) -> Response:
    horas = float(ConfigService.get("coleta_token_horas") or _HORAS_TOKEN_PADRAO)
    resp = Response(_pagina_pareamento_ok(dispositivo_label))
    resp.set_cookie(
        _COOKIE_NOME, device_token, max_age=int(horas * 3600),
        httponly=True, samesite="Lax", secure=False, path="/",
    )
    if dispositivo_id:
        resp.set_cookie(
            _COOKIE_DISPOSITIVO, dispositivo_id, max_age=_DISPOSITIVO_ID_DIAS * 86400,
            httponly=True, samesite="Lax", secure=False, path="/",
        )
    return resp


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
  label {{ display: block; font-size: 13px; color: #888780; margin: 12px 0 4px; }}
  input[type="text"], select {{ width: 100%; box-sizing: border-box; padding: 10px;
            border: 1px solid #E8E6DE; border-radius: 6px; font-size: 15px; }}
  button {{ width: 100%; margin-top: 18px; padding: 12px; border: none; border-radius: 6px;
            background: #1F5F5B; color: #fff; font-size: 15px; font-weight: bold; }}
  .rodape-link {{ display: block; text-align: center; margin: 14px 16px 0; font-size: 13px; color: #1F5F5B; }}
</style>
</head>
<body>
<div class="topo">Centro de Uro-Nefrologia — Patrimônio</div>
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
<a class="rodape-link" href="/localizacao">Trocar localização</a>
"""
    return _layout("Leitura registrada", corpo)


def _pagina_cadastro_dispositivo(convite: ConviteColeta, token: str) -> str:
    if convite.localizacao_fixa_id:
        campo_localizacao = (
            f'<label>Localização</label>'
            f'<input type="text" value="{escape(convite.localizacao_fixa)}" disabled>'
            f'<input type="hidden" name="localizacao_id" value="{convite.localizacao_fixa_id}">'
        )
    else:
        opcoes_html = "".join(
            f'<option value="{loc_id}">{escape(nome)}</option>'
            for loc_id, nome in convite.opcoes_localizacao
        )
        campo_localizacao = (
            f'<label>Onde você está agora?</label>'
            f'<select name="localizacao_id" required><option value="">Selecione...</option>{opcoes_html}</select>'
        )

    corpo = f"""
<div class="cartao">
  <p class="titulo-cartao">{escape(convite.descricao_sessao)}</p>
  <p>Cadastre este aparelho para começar a ler as etiquetas dos bens.</p>
  <form method="post" action="/parear">
    <input type="hidden" name="token" value="{escape(token)}">
    <label>Nome do aparelho (opcional)</label>
    <input type="text" name="nome" maxlength="{_LIMITE_NOME}" placeholder="ex.: Celular do João">
    {campo_localizacao}
    <button type="submit">Cadastrar e começar a coletar</button>
  </form>
</div>
"""
    return _layout("Cadastro de dispositivo", corpo)


def _pagina_pareamento_ok(dispositivo_label: str | None) -> str:
    dispositivo = f" ({escape(dispositivo_label)})" if dispositivo_label else ""
    corpo = f"""
<div class="cartao" style="background:#EAF3DE">
  <p class="titulo-cartao" style="color:#27500A">Dispositivo pareado{dispositivo}</p>
  <p>Agora é só ler a etiqueta de cada bem com a câmera do celular — a leitura
  é registrada automaticamente na sessão de inventário.</p>
</div>
<a class="rodape-link" href="/localizacao">Trocar localização</a>
"""
    return _layout("Pareamento confirmado", corpo)


def _pagina_trocar_localizacao(dados: ConviteColeta, atual_id: int) -> str:
    if dados.localizacao_fixa_id:
        corpo = f"""
<div class="cartao">
  <p class="titulo-cartao">Localização fixa</p>
  <p>Esta sessão está fixada em <strong>{escape(dados.localizacao_fixa)}</strong> — não é possível trocar.</p>
</div>
"""
        return _layout("Localização fixa", corpo)

    opcoes_html = "".join(
        f'<option value="{loc_id}"{" selected" if loc_id == atual_id else ""}>{escape(nome)}</option>'
        for loc_id, nome in dados.opcoes_localizacao
    )
    corpo = f"""
<div class="cartao">
  <p class="titulo-cartao">Trocar localização</p>
  <form method="post" action="/localizacao">
    <label>Onde você está agora?</label>
    <select name="localizacao_id" required>{opcoes_html}</select>
    <button type="submit">Confirmar</button>
  </form>
</div>
"""
    return _layout("Trocar localização", corpo)


def _pagina_localizacao_trocada() -> str:
    corpo = """
<div class="cartao" style="background:#EAF3DE">
  <p class="titulo-cartao" style="color:#27500A">Localização atualizada</p>
  <p>As próximas leituras deste aparelho já usam a nova localização.</p>
</div>
"""
    return _layout("Localização atualizada", corpo)


def _pagina_erro(titulo: str, mensagem: str, status: int) -> tuple[str, int]:
    corpo = f"""
<div class="cartao" style="background:#FCEBEB">
  <p class="titulo-cartao" style="color:#A32D2D">{escape(titulo)}</p>
  <p>{escape(mensagem)}</p>
</div>
"""
    return _layout(titulo, corpo), status
