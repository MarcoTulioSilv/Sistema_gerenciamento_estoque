@echo off
setlocal

:: ── Configuração ──────────────────────────────────────────────
set VERSION=1.0.6
set SHARE=\\192.168.0.150\SCE_Updates
if exist .env (
    for /f "tokens=2 delims==" %%s in ('findstr /b "UPDATE_SHARE=" .env') do set SHARE=%%s
)
set INSTALLER=SCE_Setup_%VERSION%.exe
:: ──────────────────────────────────────────────────────────────

echo.
echo ╔══════════════════════════════════════════╗
echo ║   SCE Uronefrologia — Build %VERSION%    ║
echo ╚══════════════════════════════════════════╝
echo.

:: 1. Limpa build anterior (varre TODAS as pastas de versao antiga, nao so a atual)
echo [1/4] Limpando build anterior...
for /d %%D in (dist\SCE_Uro_v*)  do rmdir /s /q "%%D"
for /d %%D in (build\SCE_Uro_v*) do rmdir /s /q "%%D"

:: 2. PyInstaller via .spec
:: SCE_VERSION (env var) e sce_version.txt (arquivo embutido) sao como o
:: .spec e o auto_updater.py recebem a versao sem precisar editar codigo.
echo [2/4] Empacotando com PyInstaller...
set SCE_VERSION=%VERSION%
echo %VERSION%> sce_version.txt
pyinstaller SCE_Uro_v1.spec --clean
if errorlevel 1 (
    echo ERRO no PyInstaller. Build abortado.
    pause & exit /b 1
)

:: 3. Inno Setup
echo [3/4] Gerando instalador com Inno Setup...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ^
    /DAppVersion=%VERSION% ^
    instalador\SCE_Setup.iss
if errorlevel 1 (
    echo ERRO no Inno Setup. Build abortado.
    pause & exit /b 1
)

:: 4. Publica no share para auto-updater
echo [4/4] Publicando no share de atualizacoes...
if exist "%SHARE%" (
    if exist "%SHARE%\SCE_Setup_*.exe" del /Q "%SHARE%\SCE_Setup_*.exe"
    copy /Y "dist\instalador\%INSTALLER%" "%SHARE%\%INSTALLER%"
    :: Atualiza version.json
    echo {"version": "%VERSION%", "file": "%INSTALLER%"} > "%SHARE%\version.json"
    echo Publicado em %SHARE%
) else (
    echo AVISO: Share %SHARE% inacessivel. Copie manualmente:
    echo   dist\instalador\%INSTALLER%
)

echo.
echo Build concluido: dist\instalador\%INSTALLER%
pause