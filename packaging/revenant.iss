; Inno Setup script for the Windows installer (#60).
;
;   iscc packaging\revenant.iss        (after the PyInstaller build)
;
; Installs the one-directory bundle from dist\Revenant, a Start Menu
; entry carrying the AppUserModelID the GUI stamps on its window
; (client_gui.APP_USER_MODEL_ID, "revenant.client") so the pinned icon
; and the running window share one taskbar button, and an uninstaller.
; Per-user install, no admin prompt.

#define AppName "Revenant"
#define AppVersion "0.0.1"
#define AppPublisher "revenant"
#define AppURL "https://github.com/jandersson/revenant"

[Setup]
AppId={{7D1F0C0E-9C3B-4C7A-9B2E-1A5E7C3D2B10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Revenant-{#AppVersion}-setup
SetupIconFile=..\client\client\gui\revenant.ico
UninstallDisplayIcon={app}\Revenant.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Revenant\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Revenant.exe"; AppUserModelID: "revenant.client"
Name: "{group}\{#AppName} (pick a character)"; Filename: "{app}\Revenant.exe"; Parameters: "--pick"; AppUserModelID: "revenant.client"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Revenant.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
