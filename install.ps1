# AI Note Taker - Installer
# Run via Install.bat or: powershell -ExecutionPolicy Bypass -File install.ps1

Set-Location $PSScriptRoot

function Write-Step  { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "    [X]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  AI Note Taker -- Setup" -ForegroundColor White
Write-Host "  ----------------------" -ForegroundColor DarkGray
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Python 3.11
# ---------------------------------------------------------------------------
Write-Step "Checking Python 3.11..."
try {
    $pyVer = & py -3.11 --version 2>&1
    Write-OK $pyVer
} catch {
    Write-Fail "Python 3.11 not found."
    Write-Host ""
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  During install, check 'Add Python to PATH'." -ForegroundColor Yellow
    Start-Process "https://www.python.org/downloads/"
    Read-Host "`n  Press Enter after installing Python to retry, or Ctrl+C to exit"
    try {
        $pyVer = & py -3.11 --version 2>&1
        Write-OK $pyVer
    } catch {
        Write-Fail "Still not found. Exiting."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Virtual environment
# ---------------------------------------------------------------------------
Write-Step "Setting up virtual environment..."
if (Test-Path "venv\Scripts\python.exe") {
    Write-OK "venv already exists, skipping."
} else {
    & py -3.11 -m venv venv
    if (-not $?) { Write-Fail "Failed to create venv."; exit 1 }
    Write-OK "venv created."
}

# ---------------------------------------------------------------------------
# 3. Dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing Python dependencies (this may take a few minutes)..."
& venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& venv\Scripts\pip install -r requirements.txt
if (-not $?) { Write-Fail "Dependency install failed."; exit 1 }
Write-OK "All dependencies installed."

# ---------------------------------------------------------------------------
# 4. Notes folder
# ---------------------------------------------------------------------------
Write-Step "Configure notes folder..."
$defaultPath = "$env:USERPROFILE\Documents\AI Notes"
Write-Host "    Where should notes be saved?" -ForegroundColor Gray
Write-Host "    Press Enter to use the default." -ForegroundColor Gray
Write-Host "    Default: $defaultPath" -ForegroundColor DarkGray
Write-Host ""
$notesInput = Read-Host "    Path"
$notesPath = if ($notesInput.Trim()) { $notesInput.Trim().TrimEnd('\') } else { $defaultPath }

New-Item -ItemType Directory -Force -Path $notesPath | Out-Null

$normalizedPath = $notesPath.Replace('\', '/')
$configContent  = Get-Content "config.py" -Raw
$configContent  = $configContent -replace 'NOTES_ROOT_PATH\s*=\s*"[^"]*"', "NOTES_ROOT_PATH = `"$normalizedPath`""
Set-Content "config.py" -Value $configContent -Encoding UTF8
Write-OK "Notes folder set to: $notesPath"

# ---------------------------------------------------------------------------
# 5. Ollama
# ---------------------------------------------------------------------------
Write-Step "Checking Ollama..."
$ollamaReady = $false

try {
    $null = & ollama --version 2>&1
    $ollamaReady = $true
    Write-OK "Ollama already installed."
} catch {
    Write-Warn "Ollama not found. Trying winget..."
    try {
        & winget install --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
        # Refresh PATH so ollama is findable without reopening the terminal
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path", "User")
        $null = & ollama --version 2>&1
        $ollamaReady = $true
        Write-OK "Ollama installed."
    } catch {
        Write-Warn "Automatic install failed."
        Write-Host ""
        Write-Host "    Please install Ollama manually from: https://ollama.com" -ForegroundColor Yellow
        Start-Process "https://ollama.com"
        Read-Host "    Press Enter after installing Ollama to continue"
        try {
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("Path", "User")
            $null = & ollama --version 2>&1
            $ollamaReady = $true
        } catch {
            Write-Warn "Ollama still not detected. Skipping model download."
            Write-Warn "Run 'ollama pull llama3' manually after installing Ollama."
        }
    }
}

# ---------------------------------------------------------------------------
# 6. Pull Llama 3
# ---------------------------------------------------------------------------
if ($ollamaReady) {
    Write-Step "Downloading Llama 3 model (~4.7 GB, one-time)..."
    Write-Host "    This may take several minutes depending on your connection." -ForegroundColor Gray
    & ollama pull llama3
    if ($?) { Write-OK "Llama 3 ready." } else { Write-Warn "Model download may have failed. Run 'ollama pull llama3' manually." }
}

# ---------------------------------------------------------------------------
# 7. Desktop shortcut
# ---------------------------------------------------------------------------
Write-Step "Creating desktop shortcut..."
$shortcutCreated = $false
try {
    $shell     = New-Object -ComObject WScript.Shell
    $desktop   = $shell.SpecialFolders("Desktop")
    $shortcut  = $shell.CreateShortcut("$desktop\AI Note Taker.lnk")
    $shortcut.TargetPath       = "$PSScriptRoot\Launch App.bat"
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description      = "AI Note Taker"
    $shortcut.Save()
    $shortcutCreated = $true
    Write-OK "Shortcut created on Desktop."
} catch {
    Write-Warn "Could not create shortcut. Launch via 'Launch App.bat' instead."
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ----------------------" -ForegroundColor DarkGray
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "  ----------------------" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Launch the app:" -ForegroundColor White
if ($shortcutCreated) {
    Write-Host "    Double-click 'AI Note Taker' on your Desktop" -ForegroundColor Gray
    Write-Host "    or run 'Launch App.bat' from this folder." -ForegroundColor Gray
} else {
    Write-Host "    Run 'Launch App.bat' from this folder:" -ForegroundColor Gray
    Write-Host "    $PSScriptRoot" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "  Optional -- Google Calendar integration:" -ForegroundColor White
Write-Host "    1. Go to https://console.cloud.google.com and create a project" -ForegroundColor Gray
Write-Host "    2. Enable the Google Calendar API" -ForegroundColor Gray
Write-Host "    3. APIs & Services > Credentials > Create > OAuth client ID > Desktop app" -ForegroundColor Gray
Write-Host "    4. Download the JSON, rename it to 'credentials.json', place it here:" -ForegroundColor Gray
Write-Host "       $PSScriptRoot" -ForegroundColor Cyan
Write-Host "    5. On first use a browser will open to sign in to Google -- do this once." -ForegroundColor Gray
Write-Host ""
