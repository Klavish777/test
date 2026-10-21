; Inno Setup 6 script for Smartphone Repair OS
; Build:
;   1) pyinstaller build/smartphone_repair_os.spec --noconfirm --clean
;   2) iscc build/installer.iss /DAppVersion=0.1.0
; Result: installer/Output/SmartphoneRepairOS-<version>-setup.exe

#define AppName "Smartphone Repair OS"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppPublisher "Smartphone Repair OS"
#define AppExeName "SmartphoneRepairOS.exe"
#define ProjectRoot AddBackslash(SourcePath) + ".."
#define DistDir ProjectRoot + "\dist\SmartphoneRepairOS"

[Setup]
AppId={{8F6D3A3E-2C77-4C0E-9E4A-9C31B2A15D11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Smartphone Repair OS
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#ProjectRoot}\installer\Output
OutputBaseFilename=SmartphoneRepairOS-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\installer"
