; SANTIESUN BOUT - Script de Instalador Inno Setup
; Este instalador detecta automaticamente si hay GPU NVIDIA

#define MyAppName "SANTIESUN BOUT"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SANTIESUN"
#define MyAppExeName "SANTIESUN_BOUT.exe"

[Setup]
AppId={{8F7E3D4A-1B2C-4D5E-9F0A-1B2C3D4E5F6A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Icono del instalador (descomentar si tienes icono)
; SetupIconFile=..\santiesun_bout\assets\icon.ico
OutputDir=..\dist\installer
OutputBaseFilename=SANTIESUN_BOUT_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; Tamano minimo requerido (en KB) - ajustar segun build
DiskSpanning=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
; Archivos principales de la aplicacion
Source: "..\dist\SANTIESUN_BOUT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; FFmpeg (incluir binarios)
Source: "..\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: FileExists(ExpandConstant('{src}\..\ffmpeg\ffmpeg.exe'))

[Dirs]
Name: "{app}\output"
Name: "{app}\history"
Name: "{app}\temp"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  GPUDetected: Boolean;
  GPUName: String;
  GPUInfoPage: TOutputMsgMemoWizardPage;

function DetectNvidiaGPU(): Boolean;
var
  ResultCode: Integer;
  TempFile: String;
  Lines: TArrayOfString;
begin
  Result := False;
  GPUName := '';

  TempFile := ExpandConstant('{tmp}\gpu_detect.txt');

  // Ejecutar nvidia-smi para detectar GPU
  if Exec('cmd.exe', '/c nvidia-smi --query-gpu=name --format=csv,noheader > "' + TempFile + '" 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      if LoadStringsFromFile(TempFile, Lines) then
      begin
        if GetArrayLength(Lines) > 0 then
        begin
          GPUName := Lines[0];
          if (GPUName <> '') and (Pos('NVIDIA', GPUName) > 0) then
          begin
            Result := True;
          end;
        end;
      end;
    end;
  end;

  DeleteFile(TempFile);
end;

procedure InitializeWizard();
begin
  // Detectar GPU al iniciar
  GPUDetected := DetectNvidiaGPU();

  // Crear pagina de informacion de GPU
  GPUInfoPage := CreateOutputMsgMemoPage(wpWelcome,
    'Deteccion de Hardware',
    'El instalador ha analizado tu sistema.',
    'Resultados:',
    '');

  if GPUDetected then
  begin
    GPUInfoPage.RichEditViewer.Text :=
      'Se detecto GPU NVIDIA: ' + GPUName + #13#10 +
      #13#10 +
      'Tu sistema puede aprovechar la aceleracion por GPU para ' +
      'transcribir videos hasta 5 veces mas rapido.' + #13#10 +
      #13#10 +
      'La aplicacion usara automaticamente tu GPU NVIDIA.';
  end
  else
  begin
    GPUInfoPage.RichEditViewer.Text :=
      'No se detecto GPU NVIDIA compatible.' + #13#10 +
      #13#10 +
      'La aplicacion funcionara usando el procesador (CPU).' + #13#10 +
      'La transcripcion sera mas lenta pero igualmente funcional.' + #13#10 +
      #13#10 +
      'Si tienes una GPU NVIDIA, asegurate de tener los drivers instalados.';
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Crear archivo de configuracion indicando si hay GPU
    if GPUDetected then
      SaveStringToFile(ExpandConstant('{app}\gpu_enabled.txt'), 'GPU: ' + GPUName, False)
    else
      SaveStringToFile(ExpandConstant('{app}\cpu_mode.txt'), 'CPU Mode', False);
  end;
end;
