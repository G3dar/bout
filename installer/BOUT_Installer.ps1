# BOUT Installer - PowerShell Version
# Convert to .exe with: ps2exe .\BOUT_Installer.ps1 .\BOUT_Setup.exe -noConsole -requireAdmin

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Windows.Forms

# Configuration
$AppName = "BOUT"
$AppVersion = "2.0"
$RepoUrl = "https://codeload.github.com/G3dar/bout/zip/refs/heads/master"
$InstallPath = "$env:LOCALAPPDATA\BOUT"

# GUI Functions
function Show-MessageBox {
    param([string]$Message, [string]$Title = "BOUT Installer", [string]$Type = "Info")

    $icon = switch ($Type) {
        "Error" { [System.Windows.MessageBoxImage]::Error }
        "Warning" { [System.Windows.MessageBoxImage]::Warning }
        "Question" { [System.Windows.MessageBoxImage]::Question }
        default { [System.Windows.MessageBoxImage]::Information }
    }

    [System.Windows.MessageBox]::Show($Message, $Title, [System.Windows.MessageBoxButton]::OK, $icon)
}

function Show-YesNoBox {
    param([string]$Message, [string]$Title = "BOUT Installer")

    $result = [System.Windows.MessageBox]::Show($Message, $Title, [System.Windows.MessageBoxButton]::YesNo, [System.Windows.MessageBoxImage]::Question)
    return $result -eq [System.Windows.MessageBoxResult]::Yes
}

function Show-ProgressWindow {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "BOUT - Instalando..."
    $form.Size = New-Object System.Drawing.Size(500, 200)
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false

    $label = New-Object System.Windows.Forms.Label
    $label.Location = New-Object System.Drawing.Point(20, 20)
    $label.Size = New-Object System.Drawing.Size(450, 30)
    $label.Text = "Iniciando instalacion..."
    $label.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    $form.Controls.Add($label)

    $progress = New-Object System.Windows.Forms.ProgressBar
    $progress.Location = New-Object System.Drawing.Point(20, 60)
    $progress.Size = New-Object System.Drawing.Size(440, 30)
    $progress.Style = "Marquee"
    $form.Controls.Add($progress)

    $statusLabel = New-Object System.Windows.Forms.Label
    $statusLabel.Location = New-Object System.Drawing.Point(20, 100)
    $statusLabel.Size = New-Object System.Drawing.Size(450, 50)
    $statusLabel.Text = ""
    $statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $statusLabel.ForeColor = [System.Drawing.Color]::Gray
    $form.Controls.Add($statusLabel)

    return @{
        Form = $form
        Label = $label
        Progress = $progress
        Status = $statusLabel
    }
}

function Update-Progress {
    param($Window, [string]$Text, [string]$Status = "")

    $Window.Label.Text = $Text
    $Window.Status.Text = $Status
    $Window.Form.Refresh()
    [System.Windows.Forms.Application]::DoEvents()
}

# Check functions
function Test-PythonInstalled {
    try {
        $result = python --version 2>&1
        return $result -match "Python 3\."
    } catch {
        return $false
    }
}

function Test-FFmpegInstalled {
    try {
        $result = ffmpeg -version 2>&1
        return $true
    } catch {
        return $false
    }
}

function Test-GitInstalled {
    try {
        $result = git --version 2>&1
        return $true
    } catch {
        return $false
    }
}

# Installation functions
function Install-Python {
    $url = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
    $installer = "$env:TEMP\python_installer.exe"

    Write-Host "Descargando Python..."
    Invoke-WebRequest -Uri $url -OutFile $installer

    Write-Host "Instalando Python..."
    Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait

    Remove-Item $installer -Force
}

function Install-FFmpeg {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Instalando FFmpeg con winget..."
        winget install ffmpeg --accept-source-agreements --accept-package-agreements
    } else {
        Show-MessageBox "Por favor instala FFmpeg manualmente desde: https://ffmpeg.org/download.html" "FFmpeg Requerido" "Warning"
    }
}

# Main Installation
function Start-Installation {
    # Welcome
    $welcome = Show-YesNoBox "Bienvenido al instalador de BOUT v$AppVersion`n`nEste programa instalara:`n- BOUT Video Transcription Tool`n- Dependencias de Python`n- Soporte para identificacion de hablantes`n`n¿Deseas continuar?"

    if (-not $welcome) {
        exit
    }

    # Check Python
    if (-not (Test-PythonInstalled)) {
        $installPython = Show-YesNoBox "Python 3.10+ no esta instalado.`n`n¿Deseas que lo instale automaticamente?`n(Puede tomar varios minutos)"

        if ($installPython) {
            Install-Python
            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        } else {
            Show-MessageBox "Python es requerido. Por favor instalalo desde python.org y ejecuta el instalador de nuevo." "Python Requerido" "Error"
            exit
        }
    }

    # Check FFmpeg
    if (-not (Test-FFmpegInstalled)) {
        $installFFmpeg = Show-YesNoBox "FFmpeg no esta instalado.`n`nFFmpeg es necesario para procesar video.`n¿Deseas intentar instalarlo automaticamente?"

        if ($installFFmpeg) {
            Install-FFmpeg
        } else {
            Show-MessageBox "Por favor instala FFmpeg manualmente y ejecuta el instalador de nuevo.`n`nDescargar de: https://ffmpeg.org/download.html" "FFmpeg Requerido" "Warning"
        }
    }

    # Show progress window
    $window = Show-ProgressWindow
    $window.Form.Show()

    try {
        # Create install directory
        Update-Progress $window "Creando directorio de instalacion..." $InstallPath
        if (-not (Test-Path $InstallPath)) {
            New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
        }

        # Download BOUT
        Update-Progress $window "Descargando BOUT..." "Desde GitHub..."
        $zipPath = "$env:TEMP\bout.zip"
        Invoke-WebRequest -Uri $RepoUrl -OutFile $zipPath

        # Extract
        Update-Progress $window "Extrayendo archivos..." ""
        Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
        Copy-Item -Path "$env:TEMP\bout-master\*" -Destination $InstallPath -Recurse -Force
        Remove-Item $zipPath -Force
        Remove-Item "$env:TEMP\bout-master" -Recurse -Force

        # Create virtual environment
        Update-Progress $window "Creando entorno virtual..." "Esto puede tomar un momento..."
        Push-Location $InstallPath
        python -m venv venv

        # Install dependencies
        Update-Progress $window "Instalando dependencias..." "Esto puede tomar varios minutos..."
        & "$InstallPath\venv\Scripts\pip.exe" install --upgrade pip --quiet
        & "$InstallPath\venv\Scripts\pip.exe" install -r requirements.txt --quiet

        # Install drag and drop support
        Update-Progress $window "Instalando soporte drag & drop..." ""
        & "$InstallPath\venv\Scripts\pip.exe" install tkinterdnd2 --quiet 2>$null

        Pop-Location

        # Create desktop shortcut
        Update-Progress $window "Creando acceso directo..." ""
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\BOUT.lnk")
        $Shortcut.TargetPath = "$InstallPath\BOUT.bat"
        $Shortcut.WorkingDirectory = $InstallPath
        $Shortcut.Description = "BOUT - Video Transcription"
        $Shortcut.Save()

        # Create Start Menu shortcut
        $startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BOUT"
        if (-not (Test-Path $startMenuPath)) {
            New-Item -ItemType Directory -Path $startMenuPath -Force | Out-Null
        }
        $Shortcut = $WshShell.CreateShortcut("$startMenuPath\BOUT.lnk")
        $Shortcut.TargetPath = "$InstallPath\BOUT.bat"
        $Shortcut.WorkingDirectory = $InstallPath
        $Shortcut.Save()

        $Shortcut = $WshShell.CreateShortcut("$startMenuPath\Configurar HuggingFace.lnk")
        $Shortcut.TargetPath = "$InstallPath\tutorial\setup_guide.html"
        $Shortcut.Save()

        $window.Form.Close()

        # Success!
        Show-MessageBox "BOUT se instalo correctamente!`n`nUbicacion: $InstallPath`n`nSe creo un acceso directo en tu escritorio.`n`nAhora se abrira el tutorial para configurar la identificacion de hablantes." "Instalacion Completada"

        # Open tutorial
        Start-Process "$InstallPath\tutorial\setup_guide.html"

    } catch {
        $window.Form.Close()
        Show-MessageBox "Error durante la instalacion:`n`n$($_.Exception.Message)" "Error" "Error"
    }
}

# Run
Start-Installation
