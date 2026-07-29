@echo off
REM Executa o backup uma vez, manualmente, para testar a configuracao
REM antes de agendar (ou a qualquer momento depois).
setlocal
set SCRIPT_DIR=%~dp0

python "%SCRIPT_DIR%backup_sce.py"

echo.
echo Verifique backup_sce.log nesta pasta para o resultado detalhado.
pause
