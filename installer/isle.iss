; Inno Setup 6.3+  ->  dist\Isle-Setup-<версия>.exe
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B7E9A3C2-5D41-4F8B-9E26-3A1C7D0F52E8}
AppName=Isle
AppVersion={#AppVersion}
AppPublisher=Isle
DefaultDirName={autopf}\Isle
DefaultGroupName=Isle
DisableProgramGroupPage=yes
; установка в профиль пользователя: не нужен UAC, а значит автообновление проходит тихо
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Isle-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Isle.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\Isle\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Isle"; Filename: "{app}\Isle.exe"
Name: "{autodesktop}\Isle"; Filename: "{app}\Isle.exe"; Tasks: desktopicon

[Run]
; обычная установка: галочка «Запустить Isle»
Filename: "{app}\Isle.exe"; Description: "Запустить Isle"; Flags: nowait postinstall skipifsilent
; тихое обновление из самого приложения: сразу запускаем новую версию
Filename: "{app}\Isle.exe"; Flags: nowait runasoriginaluser; Check: WizardSilent
