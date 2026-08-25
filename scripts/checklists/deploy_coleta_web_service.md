# Checklist — Deploy do ColetaWebService em produção

Serviço HTTP headless do MOD-07 (Flask + Waitress, AD-14). Roda no servidor
MySQL (192.168.0.150), separado do app desktop. Já implementado e validado
em dev (test client + celular real via hotspot). Este checklist é pra
implantar no servidor de produção — execução manual, não automatizável
remotamente.

## 1. Preparar o servidor

- [ ] Copiar o projeto atualizado (ou pelo menos `Modulo_06_dados/`,
      `Modulo_05_admin/`, `Modulo_07_patrimonio/`, `servico_patrimonio.py`,
      `requirements.txt`, `.env`) para o servidor 192.168.0.150.
- [ ] Confirmar que existe uma venv Python no servidor (ou criar uma nova:
      `python -m venv .venv`).
- [ ] Instalar dependências na venv do servidor (SEM `--user` — a tarefa
      agendada roda como SYSTEM, que não enxerga pacotes `--user`):
  ```
  "<PYTHON_EXE_DO_SERVIDOR>" -m pip install -r requirements.txt
  ```
  Agora inclui `flask==3.1.3` e `waitress==3.0.2`, novos nesta rodada.
- [ ] Confirmar `.env` configurado nesse servidor (mesma conexão MySQL já
      usada por `backup_script`/pelo próprio banco local).

## 2. Confirmar configuração no banco

- [ ] `configuracao.coleta_host` já deve ser `192.168.0.150` (o IP fixo
      desse servidor — não mudar, invalida toda etiqueta já impressa, R-08).
- [ ] `configuracao.coleta_porta` já deve ser `8080`.
- [ ] `configuracao.coleta_token_horas` já deve ser `12`.
  Se algum desses estiver ausente/errado:
  ```sql
  UPDATE configuracao SET valor = '192.168.0.150' WHERE chave = 'coleta_host';
  UPDATE configuracao SET valor = '8080' WHERE chave = 'coleta_porta';
  ```

## 3. Registrar o serviço como tarefa agendada

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

## 4. Firewall do servidor — ATENÇÃO, problema real encontrado em dev

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

## 5. Validar de ponta a ponta

- [ ] De outra máquina/celular na rede interna, testar a consulta pública
      com um bem real já cadastrado:
  ```
  http://192.168.0.150:8080/p?t=<tombo de um bem existente>
  ```
- [ ] Testar o fluxo completo de coleta: abrir uma sessão de inventário em
      T-26, parear um celular pelo QR gerado ali, ler a etiqueta de um bem
      do escopo da sessão, confirmar que o item mudou de status e que o
      contador de progresso em T-26 atualiza.
- [ ] Reiniciar o servidor (ou pelo menos a tarefa) uma vez para confirmar
      que o serviço volta sozinho no boot, sem intervenção manual — é o
      requisito central do DAS §7.3 (execução permanente).

## 6. Limpeza do ambiente de dev usado nos testes (esta máquina)

Pendências deste ciclo de teste manual, ainda não revertidas nesta máquina
de desenvolvimento:

- [ ] Remover a regra de firewall temporária criada em dev:
  ```powershell
  Remove-NetFirewallRule -DisplayName "SCE ColetaWebService (dev, temporario)"
  ```
- [ ] Confirmar que `servico_patrimonio.py` não ficou rodando em background
      nesta máquina (`netstat -ano | findstr :8080` não deve mostrar nada
      em LISTENING, a não ser que se pretenda usá-la como servidor real).
