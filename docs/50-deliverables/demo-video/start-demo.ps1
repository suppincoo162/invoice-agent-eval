# Demo environment: start the WebUI static server and print deep links for each scene.
# Usage: see start-demo.readme.md (Chinese docs).
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as ANSI,
#       so non-ASCII text can break parsing (observed 2026-11-10).
param(
    [int]$Port = 8000,
    [string]$DefaultCase = "INV-V07",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path

$webuiIndex = Join-Path $root "outputs\webui\index.html"
if (-not (Test-Path $webuiIndex)) {
    Write-Host "[ERROR] outputs/webui/index.html not found. Run: python -m invoice_eval webui ..." -ForegroundColor Red
    exit 1
}

$base = "http://127.0.0.1:$Port"

function Test-Up {
    try {
        $r = Invoke-WebRequest -Uri "$base/index.html" -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "[INFO] port $Port already listening, reusing it." -ForegroundColor Yellow
} else {
    Write-Host "[INFO] starting WebUI static server at $base (dir: outputs/webui) ..." -ForegroundColor Cyan
    Start-Process -FilePath "python" `
        -ArgumentList "-m", "http.server", "$Port", "--directory", "outputs/webui" `
        -WorkingDirectory $root -WindowStyle Hidden
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-Up) { break }
    }
    if (-not (Test-Up)) {
        Write-Host "[ERROR] server did not start within 10s. Check python availability." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[OK] server ready: $base" -ForegroundColor Green
Write-Host ""
Write-Host "Deep links for each scene (paste into the address bar while recording):" -ForegroundColor Cyan
$links = @(
    @("S4  INV-V07 summary",  "#case=INV-V07&tab=summary"),
    @("S4  INV-V07 timeline", "#case=INV-V07&tab=timeline"),
    @("S5  INV-V08 summary",  "#case=INV-V08&tab=summary"),
    @("S5  INV-V08 timeline", "#case=INV-V08&tab=timeline"),
    @("S6  INV-V04 sources",  "#case=INV-V04&tab=sources"),
    @("S7  appendices dir",   "appendices/")
)
foreach ($l in $links) {
    if ($l[1] -like "appendices/*") {
        Write-Host ("  {0,-22} {1}" -f $l[0], "$base/$($l[1])")
    } else {
        Write-Host ("  {0,-22} {1}" -f $l[0], "$base/index.html$($l[1])")
    }
}
Write-Host ""
Write-Host "Recording tips:" -ForegroundColor Cyan
Write-Host "  - Browser F11 fullscreen; hide bookmarks bar; 1920x1080 at 100% scaling."
Write-Host "  - Keep the topbar (version + commit) in frame: it is the version anchor."
Write-Host "  - Stop server: Get-NetTCPConnection -LocalPort $Port -State Listen | %{ Stop-Process -Id `$_.OwningProcess -Force }"

if (-not $NoBrowser) {
    Start-Process "$base/index.html#case=$DefaultCase&tab=summary"
}
