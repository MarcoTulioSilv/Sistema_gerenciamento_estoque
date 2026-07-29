@echo off
REM Remove a tarefa agendada "SCE_Backup_Diario" do Agendador de Tarefas.
REM Execute como Administrador.
setlocal
set NOME_TAREFA=SCE_Backup_Diario

schtasks /delete /tn "%NOME_TAREFA%" /f

if %ERRORLEVEL% EQU 0 (
    echo Tarefa "%NOME_TAREFA%" removida com sucesso.
) else (
    echo ERRO ao remover a tarefa. Execute este .bat como Administrador.
)
pause
