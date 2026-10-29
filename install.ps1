# Antigravity Telegram Remote Bridge - 1-Line Windows Installer
# Usage: irm https://raw.githubusercontent.com/DominceAseberos/Antigravity-Telegram-bridge/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🚀 Antigravity Telegram Remote Bridge - Installer" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "❌ Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://python.org and rerun this command." -ForegroundColor Yellow
    exit 1
}

# 2. Installation Directory
$installDir = Join-Path $env:USERPROFILE ".antigravity-telegram-bridge"
Write-Host "📦 Installing to: $installDir" -ForegroundColor Green

if (Test-Path $installDir) {
    Write-Host "🔄 Updating existing installation..." -ForegroundColor DarkGray
    if (Test-Path (Join-Path $installDir ".git")) {
        Push-Location $installDir
        git pull --quiet
        Pop-Location
    }
} else {
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd) {
        git clone --quiet https://github.com/DominceAseberos/Antigravity-Telegram-bridge.git $installDir
    } else {
        Write-Host "⏳ Downloading repository archive..." -ForegroundColor DarkGray
        $zipUrl = "https://github.com/DominceAseberos/Antigravity-Telegram-bridge/archive/refs/heads/main.zip"
        $zipFile = Join-Path $env:TEMP "antigravity-bridge.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
        Expand-Archive -Path $zipFile -DestinationPath $env:TEMP -Force
        $extractedDir = Join-Path $env:TEMP "Antigravity-Telegram-bridge-main"
        Move-Item -Path $extractedDir -Destination $installDir -Force
        Remove-Item $zipFile -Force -ErrorAction SilentlyContinue
    }
}

# 3. Install Dependencies
Write-Host "⏳ Installing required Python dependencies..." -ForegroundColor DarkGray
python -m pip install -r (Join-Path $installDir "requirements.txt") --quiet --disable-pip-version-check

# 4. Create Global CLI Launcher
$localBin = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$cmdLauncher = Join-Path $localBin "antigravity-bridge.cmd"
if (Test-Path $localBin) {
    "@echo off`r`npython `"$installDir\bridge.py`" %*" | Out-File -FilePath $cmdLauncher -Encoding ascii -Force
}

Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""

# 5. Run Interactive Setup Wizard
Push-Location $installDir
python setup.py
Pop-Location
