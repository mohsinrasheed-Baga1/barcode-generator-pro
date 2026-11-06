; ============================================================
;  Barcode Generator Pro v4.3.0 - Inno Setup Script
;  Produces BarcodeGeneratorPro_Setup.exe
; ============================================================

#define MyAppName "Barcode Generator Pro"
#define MyAppVersion "2.5.0"
#define MyAppPublisher "Barcode Generator"
#define MyAppExeName "BarcodeGeneratorPro.exe"
#define MyAppAssocName "Barcode Generator Pro File"

[Setup]
AppId={{B4DC0DE-1234-5678-9ABC-DEF012345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=BarcodeGeneratorPro_Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\BarcodeGeneratorPro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs

[InstallDelete]
; Remove any old files before installing new version (proper upgrade)
Type: files; Name: "{app}\BarcodeGeneratorPro.exe"
Type: filesandordirs; Name: "{app}\assets"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Barcode Generator Pro}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{%APPDATA}\BarcodeGenerator"
