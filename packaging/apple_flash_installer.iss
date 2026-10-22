; Inno Setup 6 script for Apple Flash Studio (Windows 10/11 x64)
; Сборка:
;   1) pyinstaller packaging/apple_flash_studio.spec --noconfirm --clean
;   2) iscc packaging/apple_flash_installer.iss /DAppVersion=1.0.0
; Результат: installer/Output/AppleFlashStudio-<version>-setup.exe

#define AppName "Apple Flash Studio"
#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif
#define AppPublisher "Apple Flash Studio"
#define AppExeName "AppleFlashStudio.exe"
#define ProjectRoot AddBackslash(SourcePath) + ".."
#define DistDir ProjectRoot + "\dist\AppleFlashStudio"
#define IconPath ProjectRoot + "\apple_flash\resources\apple_flash.ico"

[Setup]
AppId={{D4A97E21-6B4C-47F2-A915-7E12C88B4010}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Apple Flash Studio
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#ProjectRoot}\installer\Output
OutputBaseFilename=AppleFlashStudio-{#AppVersion}-setup
SetupIconFile={#IconPath}
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
