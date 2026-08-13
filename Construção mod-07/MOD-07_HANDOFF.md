# MOD-07 — Handoff para o Claude Code

Guia de migração do planejamento (feito no chat) para a construção (Claude Code).
Executar na ordem. Cada fase tem um critério de conclusão verificável.

---

## Antes de começar

**Backup do banco de produção.** A migração 007 é aditiva e não destrutiva, mas
o backup é a única saída se algo falhar no meio.

```bash
mysqldump -u sce_app -p --databases sce_db > backup_pre_mod07_$(date +%Y%m%d).sql
```

**Confirmar o nome real da pasta de dados.** A documentação do projeto oscila
entre `Modulo_06_dados` e `modulo_06_dados`. Verificar no repositório e usar o
nome real em todos os imports:

```bash
ls -d Modulo_06_dados modulo_06_dados 2>/dev/null
```

---

## Fase 0 — Preparar o repositório

```bash
cd C:\Users\marco\Desktop\CC\SCE_Centro_uronefrologia
git checkout Inventario
git pull

mkdir migrations
mkdir documentacao\wireframes
mkdir Modulo_07_patrimonio
```

**Concluído quando:** os três diretórios existem e a branch é `Inventario`.

---

## Fase 1 — Documentação e regras

Copiar, nesta ordem:

| Arquivo | Destino |
|---|---|
| `CLAUDE.md` | raiz do repositório |
| `ERS-ControleEstoque-v1_7.docx` | `documentacao/` |
| `DAS-ControleEstoque-v1_4.docx` | `documentacao/` |
| `wf-T23-navegacao.html` | `documentacao/wireframes/` |
| `wf-T23-T25.html` | `documentacao/wireframes/` |
| `wf-T26-T27.html` | `documentacao/wireframes/` |

O `CLAUDE.md` vai **primeiro** porque é lido automaticamente em toda sessão do
Claude Code. Sem ele, cada conversa recomeça sem as regras de arquitetura.

```bash
git add CLAUDE.md documentacao/
git commit -m "chore: documentacao MOD-07 (ERS v1.7, DAS v1.4, wireframes) e CLAUDE.md"
```

**Concluído quando:** o commit existe e `CLAUDE.md` está na raiz.

---

## Fase 2 — Ferramenta de verificação

Copiar `comparar_schema.py` para `scripts/` e rodar **antes** de qualquer
alteração, para registrar a linha de base:

```bash
python scripts/comparar_schema.py > baseline_schema.txt
```

Esperado: 8 divergências em MOD-02, nenhuma em MOD-07 (as tabelas ainda não
existem — aparecerão como "tabela ausente no banco" depois que o `models.py`
for atualizado, o que é normal até a migração rodar).

```bash
git add scripts/comparar_schema.py
git commit -m "chore: script de comparacao entre models.py e schema real"
```

**Concluído quando:** o script roda e a saída foi salva.

---

## Fase 3 — Migração de schema

**Primeiro em desenvolvimento.** Nunca direto em produção.

```bash
mysql -u sce_app -p < migrations/007_patrimonio.sql
```

Descomentar e rodar as consultas de verificação da seção `[007-11]` do próprio
script. Esperado: 8 tabelas do MOD-07 + `schema_migracao`, 23 FKs, 10 chaves em
`configuracao`.

Depois de validar, ajustar os seeds para a realidade da clínica:

```sql
UPDATE configuracao SET valor = '<IP real do servidor>'  WHERE chave = 'coleta_host';
UPDATE configuracao SET valor = '<IP da impressora>'     WHERE chave = 'etiqueta_impressora_ip';
```

> O `coleta_host` fica gravado dentro de cada QR impresso. Definir o valor
> definitivo **antes** de imprimir a primeira etiqueta (R-08 do DAS).

```bash
git add migrations/007_patrimonio.sql
git commit -m "feat/mod07: migracao de schema do modulo de patrimonio"
```

**Concluído quando:** as verificações passam no banco de desenvolvimento.

---

## Fase 4 — Models

Substituir `Modulo_06_dados/models.py` pelo arquivo entregue. Ele **preserva
integralmente** o conteúdo anterior (inclusive as quebras CRLF, para o diff
ficar limpo) e acrescenta o bloco MOD-07 ao final.

Conferir o diff antes de commitar:

```bash
git diff Modulo_06_dados/models.py
```

Esperado no diff: apenas a linha de import (`Computed, CHAR` adicionados), o
docstring do topo, e o bloco novo no fim. Nenhuma alteração nas classes
existentes.

Validar contra o banco:

```bash
python scripts/testar_sintaxe.py
python scripts/comparar_schema.py --tabelas bem_patrimonial,inventario,inventario_item,inventario_sobra,movimentacao_bem,baixa_bem,coleta_token,localizacao
```

Esperado: **nenhuma divergência**.

```bash
git add Modulo_06_dados/models.py
git commit -m "feat/mod07: models SQLAlchemy do modulo de patrimonio"
```

**Concluído quando:** o comparador não acusa divergência nas 8 tabelas novas.

---

## Fase 5 — Contratos

Copiar para `Modulo_07_patrimonio/`, nesta ordem (há dependência de import):

1. `__init__.py`
2. `excecoes.py`
3. `dto.py`
4. `patrimonio_service.py`
5. `inventario_service.py`

```bash
python scripts/testar_sintaxe.py
python -c "from Modulo_07_patrimonio.inventario_service import InventarioService; print('ok')"
```

```bash
git add Modulo_07_patrimonio/
git commit -m "feat/mod07: contratos de PatrimonioService e InventarioService"
```

**Concluído quando:** o import funciona e a sintaxe está validada.

---

## Fase 6 — Primeira sessão no Claude Code

Abrir o Claude Code na raiz do projeto. Prompt inicial sugerido:

```
Estou iniciando o Sprint 9 do MOD-07 (patrimônio). O CLAUDE.md na raiz tem as
regras do projeto.

Contexto já pronto no repositório:
- migrations/007_patrimonio.sql — schema aplicado no banco de desenvolvimento
- Modulo_06_dados/models.py — models do MOD-07 já validados contra o banco
- Modulo_07_patrimonio/*.py — contratos com assinaturas, exceções e regras
- documentacao/ — ERS v1.7, DAS v1.4 e wireframes

Antes de implementar, leia:
1. CLAUDE.md
2. Modulo_07_patrimonio/patrimonio_service.py e inventario_service.py
3. Um repo existente (ex.: Modulo_02_estoque/lote_repo.py) para pegar o padrão
   de sessão, expunge_all e tratamento de erro
4. Uma tela existente (ex.: gui/telas/t11_*.py) para o padrão de GUI

Comece implementando os repositórios do MOD-07: bem_repo.py, localizacao_repo.py
e inventario_repo.py, seguindo o padrão dos repos existentes.
```

O ponto crítico é o **item 3**: sem ler um repo existente, o código sai correto
mas com cara de outro projeto.

---

## Sprint 9 — ordem de implementação

Cada item é um commit. A ordem respeita as dependências.

| # | Entrega | Depende de |
|---|---|---|
| 1 | `bem_repo.py`, `localizacao_repo.py`, `inventario_repo.py` | models |
| 2 | `tombo_generator.py` — emissão com `SELECT ... FOR UPDATE` | repos |
| 3 | `PatrimonioService`: consulta, cadastro, edição | 1, 2 |
| 4 | `PatrimonioService`: transferência e baixa | 3 |
| 5 | `PatrimonioService`: localizações | 1 |
| 6 | T-24 cadastro de bem | 3 |
| 7 | T-23 listagem com filtros e seleção | 3 |
| 8 | T-25 movimentação, baixa e histórico | 4 |
| 9 | Navegação entre subsistemas + transição | 6, 7 |

Sprints seguintes: **S10** etiquetas (`etiqueta_builder`, três saídas) ·
**S11** inventário (`InventarioService`, T-26, serviço HTTP de coleta) ·
**S12** relatórios, testes e empacotamento.

### Por que os repos vêm primeiro

`TomboGenerator` precisa de acesso transacional a `configuracao`. Sem os repos,
ele acabaria falando com o banco por conta própria — violando a regra de que
MOD-06 é o único acessor, logo no primeiro arquivo do módulo.

### Por que a navegação vem por último no S9

A troca de subsistema mexe em `gui/app.py`, que é compartilhado com o estoque.
Fazer isso antes das telas do MOD-07 existirem deixaria o botão levando a um
menu vazio, e qualquer bug ali afeta o sistema em produção.

---

## Verificações recorrentes

Rodar após qualquer alteração de schema ou de `models.py`:

```bash
python scripts/testar_sintaxe.py
python scripts/comparar_schema.py
```

Antes de fechar o sprint, contra o banco de **produção** (somente leitura):

```bash
python scripts/comparar_schema.py --url "mysql+pymysql://sce_leitura:SENHA@192.168.0.150/sce_db"
```

---

## Pendências abertas que não bloqueiam o código

| ID | Pendência | Impacto |
|---|---|---|
| AP-16 | Material da etiqueta: térmica direta ou transferência com ribbon resina | Térmica direta desbota; o tombo é a única identidade do bem |
| AP-18 | Leitor existente é 1D ou imager 2D | Mitigado pela dupla simbologia na etiqueta |
| AP-19 | Direção ainda não decidiu entre etiqueta adesiva e plaqueta gravada | Mesmo layout atende às duas saídas |

Nenhuma altera arquitetura. Resolver quando a informação da clínica chegar.

---

## Quando voltar ao chat

Bugs, implementação e refatoração ficam no Claude Code. Voltar ao chat quando
surgir **decisão de escopo** — por exemplo, "e se o inventário precisar de
aprovação da gestora?". Discussão de requisito no meio de uma sessão de código
tende a virar implementação apressada, sem passar pela ERS.
