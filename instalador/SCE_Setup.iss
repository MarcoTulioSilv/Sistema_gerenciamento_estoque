; ================================================================
; SCE — Sistema de Controle de Estoque · Centro Uronefrologia
; Script Inno Setup 6.x
; Atualizar #define AppVersion a cada release
; ================================================================

#define AppName      "SCE - Controle de Estoque Uronefrologia"
#define AppVersion   "1.0.3"
#define AppPublisher "Centro Uronefrologia"

; 1. CORREÇÃO: Nomes dinâmicos baseados no AppVersion acima!
#define AppExeName   "SCE_Uro_v" + AppVersion + ".exe"
#define SourceDir    "..\dist\SCE_Uro_v" + AppVersion
#define AppIcon      "..\assets\Logo_Uro_sem_Nome.ico"

[Setup]
; GUID único — não alterar entre versões (identifica o app no Windows)
AppId={{A7C3F2E1-4B8D-4A1F-9C2E-3D6B8A5F1E4C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\SCE_Uronefrologia
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist\instalador
OutputBaseFilename=SCE_Setup_{#AppVersion}
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; 2. CORREÇÃO: Filtro agora procura dinamicamente pelo AppExeName correto
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

; Admin necessário para instalar em Program Files
PrivilegesRequired=admin

; Versão mínima Windows 10
MinVersion=10.0

[Languages]
Name: "brazilianportuguese"; \
  MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Criar ícone na área de trabalho"; \
  GroupDescription: "Ícones adicionais:"; \
  Flags: checkedonce

; 3. SOLUÇÃO PRINCIPAL: Deleta versões/executáveis antigos antes de instalar
[InstallDelete]
Type: files; Name: "{app}\SCE_Uro_v*.exe"
Type: files; Name: "{commondesktop}\SCE Uronefrologia.lnk"

[Files]
; Pasta completa gerada pelo PyInstaller --onedir
Source: "{#SourceDir}\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";   Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar";  Filename: "{uninstallexe}"
Name: "{commondesktop}\SCE Uronefrologia"; \
  Filename: "{app}\{#AppExeName}"; \
  IconFilename: "{app}\{#AppExeName}"; \

[Run]
; Abre o SCE após instalação normal (não executa em modo /SILENT)
Filename: "{app}\{#AppExeName}"; \
  Description: "Abrir o SCE agora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"