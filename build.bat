@echo off
setlocal

:: ── Configuração ──────────────────────────────────────────────
set VERSION=1.0.4
set SHARE=\\192.168.0.150\SCE_Updates
set INSTALLER=SCE_Setup_%VERSION%.exe
:: ──────────────────────────────────────────────────────────────

echo.
echo ╔══════════════════════════════════════════╗
echo ║   SCE Uronefrologia — Build %VERSION%    ║
echo ╚══════════════════════════════════════════╝
echo.

:: 1. Limpa build anterior
echo [1/4] Limpando build anterior...
if exist dist\SCE_Uro_v1   rmdir /s /q dist\SCE_Uro_v1
if exist build\SCE_Uro_v1  rmdir /s /q build\SCE_Uro_v1

:: 2. PyInstaller via .spec
echo [2/4] Empacotando com PyInstaller...
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