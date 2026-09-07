@echo off
REM ============================================================
REM  instalar_tarefa_coleta.bat
REM  Registra o ColetaWebService (MOD-07) no Agendador de Tarefas
REM  do Windows, para iniciar automaticamente com o servidor.
REM  Execute como Administrador, UMA VEZ, no servidor MySQL
REM  (192.168.0.150).
REM
REM  Diferente do backup diario (instalar_tarefa.bat): este servico
REM  fica em execucao PERMANENTE (waitress.serve e bloqueante), nao
REM  roda uma vez por dia -- a tarefa e "ao iniciar o sistema", sem
REM  horario e sem repeticao.
REM
REM  Pre-requisitos antes de rodar este .bat:
REM    1. Python instalado no servidor (ajuste PYTHON_EXE abaixo para o
REM       caminho completo -- a tarefa roda como SYSTEM, que tem PATH
REM       proprio e normalmente nao enxerga onde o Python foi instalado).
REM    2. Dependencias instaladas NO MESMO PYTHON_EXE abaixo, SEM --user
REM       (--user so fica visivel pro seu usuario, nao pra conta SYSTEM):
REM         "<PYTHON_EXE>" -m pip install -r requirements.txt
REM       Este .bat confere isso sozinho antes de criar a tarefa.
REM    3. .env configurado (mesmo arquivo usado pelo app desktop --
REM       o servico compartilha a mesma conexao MySQL).
REM    4. configuracao.coleta_host / coleta_porta ja definidos no banco
REM       com o IP fixo real do servidor (AD-21) -- ver
REM       Construcao mod-07\MOD-07_HANDOFF.md.
REM ============================================================
setlocal

set SCRIPT_DIR=%~dp0
REM Caminho COMPLETO do Python deste servidor -- mesma observacao de
REM instalar_tarefa.bat: a conta SYSTEM nao enxerga o PATH interativo.
set PYTHON_EXE=C:\Program Files\Python313\python.exe
set NOME_TAREFA=SCE_ColetaWebService

REM Confere se flask/waitress estao instalados NESTE python.exe especifico.
echo Verificando dependencias em "%PYTHON_EXE%"...
"%PYTHON_EXE%" -c "import flask, waitress" 2>nul
if errorlevel 1 (
    echo.
    echo ERRO: flask e/ou waitress nao estao instalados para
    echo "%PYTHON_EXE%" ^(instalados so para outro usuario/Python nao contam^).
    echo Rode primeiro, como Administrador, SEM --user:
    echo   "%PYTHON_EXE%" -m pip install -r "%SCRIPT_DIR%requirements.txt"
    echo e execute este .bat de novo.
    pause
    exit /b 1
)
echo OK - dependencias encontradas.

REM Gera um wrapper que redireciona TODA a saida (stdout+stderr) para um
REM arquivo -- inclusive erros que acontecem antes do proprio logger do
REM servico existir. O Agendador de Tarefas nao mostra stdout/stderr em
REM lugar nenhum por padrao, entao sem isso um erro fica invisivel.
> "%SCRIPT_DIR%executar_coleta.bat" (
    echo @echo off
    echo "%PYTHON_EXE%" "%SCRIPT_DIR%servico_patrimonio.py" ^> "%SCRIPT_DIR%coleta_task_stdout.log" 2^>^&1
)

schtasks /create ^
  /tn "%NOME_TAREFA%" ^
  /tr "\"%SCRIPT_DIR%executar_coleta.bat\"" ^
  /sc onstart ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Tarefa "%NOME_TAREFA%" criada com sucesso -- inicia junto com o Windows.
    echo Executando como SYSTEM ^(sem senha necessaria^) pois o servico conecta
    echo ao MySQL local e nao precisa de nenhum perfil de usuario.
    echo.
    echo Para iniciar AGORA sem reiniciar o servidor:
    echo   schtasks /run /tn "%NOME_TAREFA%"
    echo.
    echo Verifique em: Agendador de Tarefas do Windows ^> Biblioteca do Agendador de Tarefas.
    echo Se o servico nao subir: confira o arquivo
    echo   %SCRIPT_DIR%coleta_task_stdout.log
    echo e o log continuo em %%LOCALAPPDATA%%\SCE_Urofrologia\coleta_web_service.log
) else (
    echo.
    echo ERRO ao criar a tarefa. Execute este .bat como Administrador.
)
pause
