@echo off
REM ============================================================
REM  instalar_tarefa.bat
REM  Registra o backup automatico diario do SCE no Agendador de
REM  Tarefas do Windows. Execute como Administrador, UMA VEZ,
REM  no servidor (192.168.0.150).
REM
REM  Pre-requisitos antes de rodar este .bat:
REM    1. Python instalado no servidor (ajuste PYTHON_EXE abaixo para o
REM       caminho completo -- a tarefa roda como SYSTEM, que tem PATH
REM       proprio e normalmente nao enxerga onde o Python foi instalado).
REM    2. Dependencias instaladas NO MESMO PYTHON_EXE abaixo, SEM --user
REM       (--user so fica visivel pro seu usuario, nao pra conta SYSTEM):
REM         "<PYTHON_EXE>" -m pip install -r requirements.txt
REM       Este .bat confere isso sozinho antes de criar a tarefa.
REM    3. backup.env configurado (copiado de backup.env.example)
REM    4. Usuario MySQL "sce_backup" criado (ver criar_usuario_backup.sql)
REM    5. mysqldump.exe disponivel no PATH do servidor (ou MYSQLDUMP_EXE
REM       no backup.env, mesmo motivo do item 1).
REM ============================================================
setlocal

set SCRIPT_DIR=%~dp0
REM Caminho COMPLETO do Python deste servidor (nao usar so "python": a
REM tarefa roda como SYSTEM, que tem seu proprio PATH e normalmente NAO
REM enxerga onde o Python foi instalado, mesmo com o PATH do seu usuario
REM certinho). Se reinstalar/mover o Python neste servidor, atualize a
REM linha abaixo.
set PYTHON_EXE=C:\Program Files\Python313\python.exe
set HORARIO=06:30
set NOME_TAREFA=SCE_Backup_Diario

REM Confere se pymysql/python-dotenv estao instalados NESTE python.exe
REM especifico -- nao no que resolve no seu PATH interativo. Pacotes
REM instalados com "pip install --user" ficam no perfil do SEU usuario e
REM a conta SYSTEM (quem roda a tarefa de verdade) nao enxerga, causando
REM "ModuleNotFoundError" silencioso na primeira execucao agendada.
echo Verificando dependencias em "%PYTHON_EXE%"...
"%PYTHON_EXE%" -c "import pymysql, dotenv" 2>nul
if errorlevel 1 (
    echo.
    echo ERRO: pymysql e/ou python-dotenv nao estao instalados para
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
REM backup_sce.py existir (ex.: falha ao criar backup_sce.log por permissao
REM da conta SYSTEM nesta pasta). O Agendador de Tarefas nao mostra stdout/
REM stderr em lugar nenhum por padrao, entao sem isso um erro assim fica
REM invisivel (Ultimo Resultado de Execucao = 0x1, sem pista nenhuma).
> "%SCRIPT_DIR%executar_backup.bat" (
    echo @echo off
    echo "%PYTHON_EXE%" "%SCRIPT_DIR%backup_sce.py" ^> "%SCRIPT_DIR%task_stdout.log" 2^>^&1
)

schtasks /create ^
  /tn "%NOME_TAREFA%" ^
  /tr "\"%SCRIPT_DIR%executar_backup.bat\"" ^
  /sc daily ^
  /st %HORARIO% ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Tarefa "%NOME_TAREFA%" criada com sucesso, agendada para %HORARIO% diariamente.
    echo Executando como SYSTEM ^(sem senha necessaria^) pois o script grava em
    echo disco local e conecta ao MySQL local ^(127.0.0.1^).
    echo Verifique em: Agendador de Tarefas do Windows ^> Biblioteca do Agendador de Tarefas.
    echo.
    echo Se "Executar agora" nao gerar backup: confira o arquivo
    echo   %SCRIPT_DIR%task_stdout.log
    echo depois de rodar -- ele mostra a saida bruta ^(inclusive erro do
    echo Python^) mesmo quando o proprio backup_sce.log nunca chega a existir.
) else (
    echo.
    echo ERRO ao criar a tarefa. Execute este .bat como Administrador.
)
pause
