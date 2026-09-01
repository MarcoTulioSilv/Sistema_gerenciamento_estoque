# Checklist — Deploy do ColetaWebService em produção

Serviço HTTP headless do MOD-07 (Flask + Waitress, AD-14). Roda no servidor
MySQL (192.168.0.150), separado do app desktop. Já implementado e validado
em dev (test client + celular real via hotspot). Este checklist é pra
implantar no servidor de produção — execução manual, não automatizável
remotamente.

## 1. Preparar o servidor

- [ ] Copiar o projeto atualizado (ou pelo menos `Modulo_06_dados/`,
      `Modulo_05_admin/`, `Modulo_07_patrimonio/`, `assets/`,
      `servico_patrimonio.py`, `fuso_horario.py`, `requirements.txt`,
      `.env`) para o servidor 192.168.0.150.
      `fuso_horario.py` é novo nesta rodada e fica solto na raiz do
      projeto (não dentro de nenhum `Modulo_XX`) — é importado por
      `Modulo_05_admin/usuario_service.py` (carregado assim que
      `Modulo_05_admin` é importado), então esquecê-lo derruba o serviço
      logo na inicialização com `ModuleNotFoundError`. `assets/` também é
      novo na lista: `Modulo_07_patrimonio/etiqueta_builder.py` agora lê
      um ícone de lá (`assets/etiqueta_logo_icone.png`) — não é usado
      pelas rotas HTTP do serviço hoje, mas evita um `FileNotFoundError`
      se isso mudar.
- [ ] Confirmar que existe uma venv Python no servidor (ou criar uma nova:
      `python -m venv .venv`).
- [ ] Instalar dependências na venv do servidor (SEM `--user` — a tarefa
      agendada roda como SYSTEM, que não enxerga pacotes `--user`):
  ```
  "<PYTHON_EXE_DO_SERVIDOR>" -m pip install -r requirements.txt
  ```
  Inclui `flask`, `waitress` (serviço em si) e, desde a rodada do
  pareamento em duas fases, `Pillow` (converte o ícone da clínica pro
  bitmap `^GFA` das etiquetas — mesma lib que o app desktop já usa via
  customtkinter, mas aqui é dependência direta do servidor headless).
- [ ] Confirmar `.env` configurado nesse servidor (mesma conexão MySQL já
      usada por `backup_script`/pelo próprio banco local).

## 2. Aplicar a migração de banco — OBRIGATÓRIO antes de subir o serviço

O pareamento em duas fases (convite fixo da sessão + cadastro pelo
celular) depende de uma tabela nova (`coleta_convite`) e uma coluna nova
em `coleta_token` (`dispositivo_id`). **Sem isso, o serviço sobe
normalmente, mas todo `GET/POST /parear` quebra** assim que alguém tenta
ler o QR — a query bate numa tabela que não existe.

- [ ] Rodar `documentacao/migrations/010_patrimonio_convite_dispositivo.sql`
      contra o banco de produção **antes** de iniciar/reiniciar a tarefa
      agendada com o código novo. É aditiva e reexecutável (mesmo padrão
      das migrações 007-009) — pode rodar mesmo que já tenha sido
      aplicada por engano.
- [ ] Rodar também `documentacao/migrations/011_patrimonio_log.sql`
      (tabela `log_patrimonio`, T-30). A rota `POST /parear` deste mesmo
      serviço grava um evento `dispositivo_pareado` nela a cada pareamento
      confirmado — sem essa tabela, o **primeiro** celular a confirmar o
      cadastro quebra a requisição (tabela inexistente), mesmo com a 010
      já aplicada.
- [ ] Conferir que aplicou: a tabela `coleta_convite` existe,
      `coleta_token` tem a coluna `dispositivo_id`, e a tabela
      `log_patrimonio` existe.
  ```sql
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = 'sce_db' AND TABLE_NAME = 'coleta_convite';
  SELECT COUNT(*) FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = 'sce_db' AND TABLE_NAME = 'coleta_token'
     AND COLUMN_NAME = 'dispositivo_id';
  SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA = 'sce_db' AND TABLE_NAME = 'log_patrimonio';
  ```
  As três devem devolver `1`.

## 3. Confirmar configuração no banco

- [ ] `configuracao.coleta_host` já deve ser `192.168.0.150` (o IP fixo
      desse servidor — não mudar, invalida toda etiqueta já impressa, R-08).
- [ ] `configuracao.coleta_porta` já deve ser `8080`.
- [ ] `configuracao.coleta_token_horas` já deve ser `12`.
  Se algum desses estiver ausente/errado:
  ```sql
  UPDATE configuracao SET valor = '192.168.0.150' WHERE chave = 'coleta_host';
  UPDATE configuracao SET valor = '8080' WHERE chave = 'coleta_porta';
  ```

## 4. Registrar o serviço como tarefa agendada

- [ ] Abrir `instalar_tarefa_coleta.bat` e ajustar a linha `PYTHON_EXE` para
      o caminho real do Python **nesse servidor** (a tarefa roda como
      SYSTEM, que tem PATH próprio — não confiar em `python` genérico).
- [ ] Executar `instalar_tarefa_coleta.bat` **como Administrador**, no
      próprio servidor.
- [ ] Confirmar que o script encontrou `flask`/`waitress` instalados (o
      `.bat` já checa isso sozinho antes de criar a tarefa).
- [ ] Rodar a tarefa uma vez manualmente pra validar antes de depender do
      boot automático:
  ```
  schtasks /run /tn "SCE_ColetaWebService"
  ```
- [ ] Conferir que subiu, sem erro, em dois lugares:
  - `coleta_task_stdout.log` (na mesma pasta do `.bat` — captura erro que
    acontece antes do logger do próprio serviço existir)
  - `%LOCALAPPDATA%\SCE_Urofrologia\coleta_web_service.log` (log contínuo,
    com rotação)

## 5. Firewall do servidor — ATENÇÃO, problema real encontrado em dev

Durante o teste em ambiente de desenvolvimento, o Windows bloqueou TODA
conexão de entrada mesmo com uma regra específica liberando a porta 8080,
porque o perfil de rede ativo (**Público**) estava com **"Bloquear todas as
conexões de entrada"** ligado (`netsh advfirewall show publicprofile
firewallpolicy` mostrando `BlockInboundAlways`) — isso ignora qualquer
regra individual. O perfil **Particular** não tem esse bloqueio total.
Verificar isso no servidor **antes** de concluir que "não funciona":

- [ ] Checar a categoria da rede ativa no servidor:
  ```powershell
  Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory
  ```
- [ ] Checar se o perfil correspondente tem bloqueio total:
  ```powershell
  netsh advfirewall show publicprofile firewallpolicy
  netsh advfirewall show privateprofile firewallpolicy
  ```
  Se aparecer `BlockInboundAlways` no perfil da rede ativa do servidor,
  duas opções (escolher a mais adequada à política de segurança de lá):
  - Reclassificar a rede do servidor como Particular (mais cirúrgico, não
    mexe na postura de outras redes), **ou**
  - Desativar o bloqueio total só naquele perfil específico:
    ```
    netsh advfirewall set publicprofile firewallpolicy blockinbound,allowoutbound
    ```
- [ ] Criar (se ainda não existir) uma regra de entrada permanente pra
      porta 8080/TCP, como Administrador:
  ```powershell
  New-NetFirewallRule -DisplayName "SCE ColetaWebService" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Any
  ```
  (Diferente da regra criada em dev — essa é permanente, não remover
  depois.)
- [ ] Confirmar que a porta 8080 do servidor está liberada também no
      roteador/switch da rede da clínica para a rede interna (DAS v1.5
      §7.2 — "porta do serviço de coleta liberada no firewall do servidor
      para a rede interna, e somente para ela").

## 6. Validar de ponta a ponta

- [ ] De outra máquina/celular na rede interna, testar a consulta pública
      com um bem real já cadastrado:
  ```
  http://192.168.0.150:8080/p?t=<tombo de um bem existente>
  ```
- [ ] Testar o fluxo completo de pareamento em duas fases (não é mais um
      token direto por QR): abrir uma sessão em T-26, ir pro estágio de
      coleta — o QR ali é um **convite fixo da sessão**, sempre o mesmo
      enquanto ela estiver aberta. Ler com a câmera do celular deve abrir
      um formulário simples (nome do aparelho e, se a sessão for de
      escopo geral, a localização); confirmar aí é que cria o pareamento
      de verdade — só a partir desse ponto o aparelho aparece em
      "Dispositivos ativos" em T-26. Reabrir o mesmo link no mesmo
      celular depois deve reconectar direto, sem mostrar o formulário de
      novo nem duplicar o aparelho na lista.
- [ ] Conferir em T-30 (Log de Patrimônio, menu TI) que esse pareamento
      gerou exatamente UMA linha "Dispositivo pareado" — e que reabrir o
      link no mesmo celular (passo anterior) não gerou uma segunda.
- [ ] Ler a etiqueta de um bem do escopo da sessão a partir do celular já
      pareado, confirmar que o item mudou de status e que o contador de
      progresso em T-26 atualiza (via polling, até 4s de atraso).
- [ ] Reiniciar o servidor (ou pelo menos a tarefa) uma vez para confirmar
      que o serviço volta sozinho no boot, sem intervenção manual — é o
      requisito central do DAS §7.3 (execução permanente).

## 7. Limpeza do ambiente de dev usado nos testes (esta máquina)

Pendências deste ciclo de teste manual, ainda não revertidas nesta máquina
de desenvolvimento:

- [ ] Remover a regra de firewall temporária criada em dev:
  ```powershell
  Remove-NetFirewallRule -DisplayName "SCE ColetaWebService (dev, temporario)"
  ```
- [ ] Confirmar que `servico_patrimonio.py` não ficou rodando em background
      nesta máquina (`netstat -ano | findstr :8080` não deve mostrar nada
      em LISTENING, a não ser que se pretenda usá-la como servidor real).
