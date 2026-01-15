; BOUT Installer Script for Inno Setup
; Compile with Inno Setup Compiler (free): https://jrsoftware.org/isinfo.php

#define MyAppName "BOUT"
#define MyAppVersion "2.0"
#define MyAppPublisher "BOUT"
#define MyAppExeName "BOUT.bat"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=BOUT_Setup
SetupIconFile=..\bout_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Iconos adicionales:"; Flags: unchecked

[Files]
; Main application files
Source: "..\bout\*"; DestDir: "{app}\bout"; Flags: ignoreversion recursesubdirs
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\BOUT.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\setup.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\tutorial\*"; DestDir: "{app}\tutorial"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\BOUT"; Filename: "{app}\BOUT.bat"; WorkingDir: "{app}"
Name: "{group}\Configurar HuggingFace"; Filename: "{app}\tutorial\setup_guide.html"
Name: "{group}\Desinstalar BOUT"; Filename: "{uninstallexe}"
Name: "{commondesktop}\BOUT"; Filename: "{app}\BOUT.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Post-install: run setup
Filename: "{app}\tutorial\setup_guide.html"; Description: "Abrir tutorial de configuracion"; Flags: postinstall shellexec skipifsilent
Filename: "{cmd}"; Parameters: "/c ""{app}\setup.bat"""; Description: "Instalar dependencias de Python"; Flags: postinstall runhidden waituntilterminated

[Code]
var
  PythonPage: TInputQueryWizardPage;
  FFmpegPage: TOutputMsgMemoWizardPage;

function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function IsFFmpegInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('ffmpeg', '-version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

procedure InitializeWizard;
begin
  // Check Python
  if not IsPythonInstalled() then
  begin
    MsgBox('Python no esta instalado.' + #13#10 + #13#10 +
           'Por favor descarga e instala Python 3.10 o superior desde:' + #13#10 +
           'https://www.python.org/downloads/' + #13#10 + #13#10 +
           'IMPORTANTE: Marca la opcion "Add Python to PATH"',
           mbInformation, MB_OK);
  end;

  // Check FFmpeg
  if not IsFFmpegInstalled() then
  begin
    MsgBox('FFmpeg no esta instalado.' + #13#10 + #13#10 +
           'FFmpeg es necesario para procesar video.' + #13#10 +
           'Puedes instalarlo con: winget install ffmpeg' + #13#10 +
           'O descargarlo de: https://ffmpeg.org/download.html',
           mbInformation, MB_OK);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\jobs"
