# BOUT Installer - PowerShell Version
# Simple and robust installer

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Windows.Forms

# Configuration
$AppName = "BOUT"
$AppVersion = "2.0"
$RepoUrl = "https://codeload.github.com/G3dar/bout/zip/refs/heads/master"
$InstallPath = "$env:LOCALAPPDATA\BOUT"

function Show-Message {
    param([string]$Message, [string]$Title = "BOUT Installer")
    [System.Windows.MessageBox]::Show($Message, $Title, "OK", "Information")
}

function Show-Error {
    param([string]$Message, [string]$Title = "BOUT Installer")
    [System.Windows.MessageBox]::Show($Message, $Title, "OK", "Error")
}

function Show-Question {
    param([string]$Message, [string]$Title = "BOUT Installer")
    $result = [System.Windows.MessageBox]::Show($Message, $Title, "YesNo", "Question")
    return $result -eq "Yes"
}

# Check Python
function Test-Python {
    try {
        $output = & python --version 2>&1
        return $output -match "Python 3"
    } catch {
        return $false
    }
}

# Kill any running BOUT processes
function Stop-BoutProcesses {
    # Kill any Python processes running from the BOUT folder
    Get-Process python*, pythonw* -ErrorAction SilentlyContinue | ForEach-Object {
        $procPath = $_.Path
        if ($procPath -and $procPath -like "*BOUT*") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    # Wait a moment for processes to terminate
    Start-Sleep -Seconds 2
}

# Safely remove installation folder
function Remove-InstallFolder {
    param([string]$Path)

    if (Test-Path $Path) {
        # First try normal removal
        try {
            Remove-Item $Path -Recurse -Force -ErrorAction Stop
            return $true
        } catch {
            # If failed, try to rename it first
            $backupPath = "$Path.old_$(Get-Date -Format 'yyyyMMddHHmmss')"
            try {
                Rename-Item $Path $backupPath -Force -ErrorAction Stop
                Remove-Item $backupPath -Recurse -Force -ErrorAction SilentlyContinue
                return $true
            } catch {
                return $false
            }
        }
    }
    return $true
}

# Main
$continue = Show-Question "Bienvenido al instalador de BOUT v$AppVersion`n`nEste programa instalara el transcriptor de video con identificacion de hablantes.`n`n¿Deseas continuar?"

if (-not $continue) { exit }

# Check Python
if (-not (Test-Python)) {
    Show-Error "Python 3 no esta instalado.`n`nPor favor instala Python desde:`nhttps://www.python.org/downloads/`n`nIMPORTANTE: Marca 'Add Python to PATH'"
    Start-Process "https://www.python.org/downloads/"
    exit
}

# Create progress form
$form = New-Object System.Windows.Forms.Form
$form.Text = "BOUT - Instalando..."
$form.Size = New-Object System.Drawing.Size(450, 150)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.ControlBox = $false

$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(20, 30)
$label.Size = New-Object System.Drawing.Size(400, 30)
$label.Text = "Descargando BOUT..."
$label.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$form.Controls.Add($label)

$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Location = New-Object System.Drawing.Point(20, 70)
$progress.Size = New-Object System.Drawing.Size(390, 25)
$progress.Style = "Marquee"
$form.Controls.Add($progress)

$form.Show()
$form.Refresh()

try {
    # Stop any running BOUT processes
    $label.Text = "Preparando instalacion..."
    $form.Refresh()
    Stop-BoutProcesses

    # Remove existing installation
    $label.Text = "Limpiando instalacion anterior..."
    $form.Refresh()
    if (-not (Remove-InstallFolder $InstallPath)) {
        $form.Close()
        Show-Error "No se puede eliminar la instalacion anterior.`n`nPor favor cierra todas las ventanas de BOUT y vuelve a intentar.`n`nSi el problema persiste, reinicia el equipo."
        exit
    }

    # Create directory
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null

    # Download
    $label.Text = "Descargando desde GitHub..."
    $form.Refresh()
    $zipPath = "$env:TEMP\bout_download.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    (New-Object System.Net.WebClient).DownloadFile($RepoUrl, $zipPath)

    # Extract
    $label.Text = "Extrayendo archivos..."
    $form.Refresh()
    Expand-Archive -Path $zipPath -DestinationPath "$env:TEMP\bout_extract" -Force
    Copy-Item -Path "$env:TEMP\bout_extract\bout-master\*" -Destination $InstallPath -Recurse -Force
    Remove-Item $zipPath -Force
    Remove-Item "$env:TEMP\bout_extract" -Recurse -Force

    # Create venv
    $label.Text = "Creando entorno virtual..."
    $form.Refresh()
    Start-Process -FilePath "python" -ArgumentList "-m venv `"$InstallPath\venv`"" -Wait -NoNewWindow

    # Create install batch script
    $batchScript = @"
@echo off
cd /d "$InstallPath"
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install tkinterdnd2
"@
    $batchPath = "$InstallPath\install_deps.bat"
    Set-Content -Path $batchPath -Value $batchScript

    # Run install script
    $label.Text = "Instalando dependencias (puede tomar varios minutos)..."
    $form.Refresh()
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$batchPath`"" -Wait -WindowStyle Hidden

    # Create desktop shortcut
    $label.Text = "Creando accesos directos..."
    $form.Refresh()
    $WshShell = New-Object -ComObject WScript.Shell

    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\BOUT.lnk")
    $Shortcut.TargetPath = "$InstallPath\BOUT.bat"
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Description = "BOUT - Video Transcription"
    $Shortcut.Save()

    # Start menu
    $startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BOUT"
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null

    $Shortcut = $WshShell.CreateShortcut("$startMenu\BOUT.lnk")
    $Shortcut.TargetPath = "$InstallPath\BOUT.bat"
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Save()

    $Shortcut = $WshShell.CreateShortcut("$startMenu\Configurar HuggingFace.lnk")
    $Shortcut.TargetPath = "$InstallPath\tutorial\setup_guide.html"
    $Shortcut.Save()

    $form.Close()

    Show-Message "BOUT instalado correctamente!`n`nUbicacion: $InstallPath`n`nSe creo un acceso directo en tu escritorio.`n`nAhora se abrira el tutorial para configurar la identificacion de hablantes."

    # Open tutorial
    Start-Process "$InstallPath\tutorial\setup_guide.html"

} catch {
    $form.Close()
    Show-Error "Error durante la instalacion:`n`n$($_.Exception.Message)"
}
