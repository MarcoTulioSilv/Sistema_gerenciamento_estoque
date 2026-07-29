@echo off
REM ============================================================
REM  instalar_tarefa.bat
REM  Registra o backup automatico diario do SCE no Agendador de
REM  Tarefas do Windows. Execute como Administrador, UMA VEZ,
REM  no servidor (192.168.0.150).
REM
REM  Pre-requisitos antes de rodar este .bat:
REM    1. Python instalado no servidor e disponivel no PATH
REM       (ou ajuste PYTHON_EXE abaixo para o caminho completo).
REM    2. pip install -r requirements.txt   (nesta pasta)
REM    3. backup.env configurado (copiado de backup.env.example)
REM    4. Usuario MySQL "sce_backup" criado (ver criar_usuario_backup.sql)
REM    5. mysqldump.exe disponivel no PATH do servidor.
REM ============================================================
setlocal

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=python
set HORARIO=06:30
set NOME_TAREFA=SCE_Backup_Diario

schtasks /create ^
  /tn "%NOME_TAREFA%" ^
  /tr "\"%PYTHON_EXE%\" \"%SCRIPT_DIR%backup_sce.py\"" ^
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
) else (
    echo.
    echo ERRO ao criar a tarefa. Execute este .bat como Administrador.
)
pause
