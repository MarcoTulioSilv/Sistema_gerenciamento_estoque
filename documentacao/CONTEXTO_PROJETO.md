# SCE — Contexto do Projeto (snapshot para retomar em outro canal)

> Documento de contexto, não é a documentação oficial do projeto (essa é o `README.md`). Serve pra colar em outra conversa/IA e dar o estado real do sistema sem precisar re-explorar o repositório do zero. Gerado a partir do estado do código em 04/08/2026, branch `Inventario`.

## O que é o SCE
Sistema de Controle de Estoque desktop para o **Centro de Uronefrologia** — rastreabilidade de insumos e medicamentos (EAN, lotes, validade, fracionamento), voltado a exigências tipo ANVISA. Aplicação Windows, um único MySQL compartilhado por todas as estações, sem nuvem.

## Stack
- **Python 3.11+**, GUI em **CustomTkinter + Tkinter** nativo.
- **MySQL + SQLAlchemy 2.0 (ORM) + PyMySQL**, sessões explícitas (`get_session`/`get_read_session`, ver `Modulo_06_dados/database.py`).
- **APScheduler** (`Modulo_04_notificacoes/scheduler.py`) pra notificações diárias e relatórios agendados.
- **OpenPyXL** pra geração de relatórios `.xlsx` (com marca d'água injetada via manipulação OOXML crua) + **GmailClient** (SMTP) pro envio.
- **PyInstaller** (`--onedir`) + **Inno Setup 6** pro instalador, com auto-updater próprio (`auto_updater.py`) que checa um `version.json` num share de rede.
- Scraper em JS (`extensao_sce/`) pra capturar DANFE do portal SEFAZ.

## Arquitetura — Separação de Camadas (agora aplicada de verdade)
Regra do projeto: **a GUI nunca deve acessar o banco diretamente** — sempre via camada de Service. Essa regra existia só como intenção documentada até uma rodada recente de correções; hoje está **efetivamente aplicada** em todas as 7 telas que violavam isso antes (t02, t09, t10, t13, t18, t19, t21, t22 — algumas delas). Fluxo padrão:

```
gui/telas/*.py  →  Modulo_0X_*/xxx_service.py  →  Modulo_0X_*/xxx_repo.py  →  Modulo_06_dados (get_session/get_read_session)
```

- Telas nunca importam `Modulo_06_dados` nem fazem `session.query`.
- Repos fazem a query crua (com `get_session`/`get_read_session`), sempre `expunge_all()` antes de devolver objetos pra fora da sessão.
- Services orquestram, validam regra de negócio, e são o único ponto que a GUI importa.

## Mapa de módulos
```
Modulo_01_autenticacao/   # RBAC, login, sessão — AuthService, SessionManager, PermissionGuard
Modulo_02_estoque/        # EstoqueService (produtos, lotes, entrada, retirada, TRANSFERÊNCIA, NF-e/DANFE),
                           # ProdutoRepo, LoteRepo (+ MovimentacaoRepo), FEFOSelector, PlanoManual
Modulo_03_relatorios/     # RelatorioService (5 relatórios: movimentação, estoque atual, a vencer,
                           # lotes vencidos, CONSUMO MÉDIO), XlsxBuilder, GrupoConsumoRepo
Modulo_04_notificacoes/   # NotificacaoService (alertas de vencimento/estoque baixo por e-mail),
                           # scheduler (APScheduler), GmailClient, JobLogRepo
Modulo_05_admin/          # UsuarioService, ConfigService, BackupManager (backup manual via T-18)
Modulo_06_dados/          # SQLAlchemy: database.py (engine/sessão) + models.py (todas as tabelas)
gui/
├── app.py                # janela raiz, roteamento de telas, scheduler
├── componentes/           # FeedbackBanner, Campos, form_widgets, tema.py (paleta de cores ÚNICA)
└── telas/                 # t01 a t22 — cada tela só importa *_service
backup_script/             # backup_sce.py standalone (roda no servidor via Agendador de Tarefas do
                           # Windows, fora do app principal) + scripts de instalação da tarefa
instalador/                # SCE_Setup.iss (Inno Setup)
documentacao/               # DDL_SCE_v1.4_.sql (schema real, reverse-engineered), ERS, DAS
scripts/                   # utilitários avulsos (testar_sintaxe.py)
```

## Padrões estabelecidos
- **Paleta de cores**: uma fonte só, `gui/componentes/tema.py` — antes cada tela redefinia as mesmas cores.
- **Nomenclatura**: snake_case consistente (havia camelCase remanescente em `gui/app.py`, corrigido).
- **Logging**: `logging` em todo lugar, sem `print()` de produção (havia alguns, corrigidos).
- **Grupos de consumo**: telas de relatório permitem agrupar produtos "irmãos" (mesmo item, marcas
  diferentes) por palavra-chave — tabela `grupo_consumo`, gerenciada por popup em T-11 (criar/editar/remover).
- **Índices/colunas de mês em relatórios**: `RelatorioService.buscar_dados_consumo_medio` já lida com
  o sistema estar em produção há pouco tempo — meses sem dado real aparecem como "—", não como "0",
  pra não distorcer a média.

## Banco de dados — atenção a isso
O schema real de produção **diverge do que já esteve documentado** em mais de uma ocasião nesta
jornada (índices, nulidade de `data_vencimento`, view `vw_saldo_produtos`, constraint única de `lote`).
`documentacao/DDL_SCE_v1.4_.sql` foi reverse-engineered do banco real e é a referência mais confiável hoje,
mas **não confie cegamente em nenhum DDL versionado sem cruzar com o modelo SQLAlchemy** — historicamente
os dois já divergiram várias vezes. Ponto específico em aberto: o commit mais recente (`eaa63f4`) menciona
ter criado uma `UNIQUE KEY (nota_fiscal, produto_id, centro_alocacao)` na tabela `lote` diretamente em
produção, mas essa constraint **não está declarada em `Modulo_06_dados/models.py`** — divergência conhecida,
ainda não fechada.

## Pipeline de build/deploy
Antes desta rodada de correções, a versão do release existia hardcoded em 4 lugares (`build.bat`,
`SCE_Uro_v1.spec`, `instalador/SCE_Setup.iss`, `auto_updater.py`), e o `/DAppVersion` que o `build.bat`
mandava pro Inno Setup **não tinha efeito nenhum** (o `.iss` sempre sobrescrevia). Corrigido: `build.bat`
(`set VERSION=...`) é a única fonte de verdade agora — o `.spec` lê `SCE_VERSION` (env var), o `.iss` usa
`#ifndef` pra respeitar o `/D`, e o `auto_updater.py` lê um `sce_version.txt` embutido no bundle no lugar
de uma constante hardcoded.

## Backup automático — pendência real, não resolvida
Tarefa `SCE_Backup_Diario` no Agendador de Tarefas do servidor (192.168.0.150) não estava rodando.
Já corrigido: caminho do Python era resolvido incorretamente (achava o alias do Microsoft Store), e
`mysqldump` também era chamado sem caminho completo (mesma classe de problema, mitigado com uma
variável `MYSQLDUMP_EXE` opcional em `backup.env`). **Ainda não confirmado que a tarefa está rodando de
verdade** — o próximo passo diagnóstico é olhar a coluna "Último Resultado de Execução" no Agendador de
Tarefas pra pegar o código de erro exato, em vez de continuar tentando às cegas.

## Estado do Git
- `main` — atualizado, todas as branches antigas (`feat/V1.0*`, `feat/auto_atualiza`, `update/V1.0.5`)
  já foram mergeadas e apagadas (local e remoto).
- `Inventario` (branch atual) — `main` + 1 commit (`eaa63f4`, o fix de transferência + limpeza de
  docs antigos). Ainda não mergeada de volta pra `main`. O nome sugere trabalho futuro de
  inventário/auditoria de estoque ainda não iniciado — não há código relacionado a isso ainda.

## Trabalho recente (ordem cronológica, mesma sessão de correções)
1. Revisão geral do projeto → 4 categorias de débito técnico levantadas (código sem uso, backend na
   GUI, despadronização, eficiência).
2. Correção de SoC: 7 telas migradas pra usar a camada de serviço.
3. Despadronização: paleta de cores centralizada, camelCase→snake_case, print→logging, cobertura de
   `try/except` faltando, IP hardcoded do auto-updater virou configurável via `.env`.
4. Eficiência: N+1 em `NotificacaoService` (envio de alertas), índices de banco reais adicionados.
5. Bugfix: `vw_saldo_produtos` zerava produtos "de consumo" (sem data de vencimento) — view corrigida.
6. Feature nova: relatório de **Consumo Médio** (T-11) — presets de 3/6 meses, colunas por mês,
   agrupamento por palavra-chave (`grupo_consumo`), exportação XLSX com título mesclado e congelamento
   de painel corrigido, download direto além de envio por e-mail.
7. Pipeline de build/deploy: fonte única de versão (ver seção acima).
8. Troubleshooting do backup automático no servidor (ver seção acima — em aberto).
9. Bugfix: transferência parcial de lote entre centros de alocação não fazia efeito nenhum, sem erro
   visível — causa raiz era uma busca subespecificada em `EstoqueService.registrar_transferencia` que
   acabava reencontrando (e "desfazendo") a própria linha de origem. Corrigido + reforçado com UK em
   produção.

## Débitos técnicos conhecidos (não corrigidos, intencionalmente fora de escopo até agora)
- `UNIQUE KEY (nota_fiscal, produto_id, centro_alocacao)` criada em produção mas ausente no modelo ORM.
- Duplicação de gravação de `JobLog` em 3 lugares diferentes (`backup_manager`, `notificacao_service`,
  `relatorio_service`).
- Duas implementações de hash bcrypt coexistindo (`AuthService` vs `UsuarioService`).
- Fracionamento de lote transferido pro mesmo centro de destino que uma transferência não-fracionada
  do mesmo lote pode colidir (edge case raro, não reportado como problema real).