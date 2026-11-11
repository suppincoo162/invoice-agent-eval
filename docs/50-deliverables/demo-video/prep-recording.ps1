# Recording prep: start WebUI, open the windows you will record, print the shot list.
# Keep this file ASCII-only (Windows PowerShell 5.1 reads .ps1 as ANSI).
# Usage:
#   powershell -ExecutionPolicy Bypass -File docs\50-deliverables\demo-video\prep-recording.ps1
#   ... prep-recording.ps1 -DryRun     # print only, open nothing
param(
    [int]$Port = 8000,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$webui = Join-Path $root "outputs\webui\index.html"
$pkg   = Join-Path $root "outputs\submission-package-v0.3.0"
$slides = Join-Path $scriptDir "slides"
$base = "http://127.0.0.1:$Port"

if (-not (Test-Path $webui)) { Write-Host "[ERROR] missing outputs/webui/index.html" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $pkg))   { Write-Host "[ERROR] missing outputs/submission-package-v0.3.0" -ForegroundColor Red; exit 1 }

function Test-Up {
    try { (Invoke-WebRequest -Uri "$base/index.html" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 }
    catch { $false }
}

Write-Host "[1/4] WebUI server ..." -ForegroundColor Cyan
if (Test-Up) {
    Write-Host "      port $Port already serving, reuse." -ForegroundColor Yellow
} elseif ($DryRun) {
    Write-Host "      [dry-run] would start: python -m http.server $Port --directory outputs/webui"
} else {
    Start-Process -FilePath "python" -ArgumentList "-m","http.server","$Port","--directory","outputs/webui" -WorkingDirectory $root -WindowStyle Hidden
    $i = 0
    while ($i -lt 40 -and -not (Test-Up)) { Start-Sleep -Milliseconds 250; $i++ }
    if (-not (Test-Up)) { Write-Host "[ERROR] server did not start" -ForegroundColor Red; exit 1 }
    Write-Host "      ready: $base" -ForegroundColor Green
}

Write-Host "[2/4] Copy cue: shot list (see RECORDING-RUNBOOK.md section 4)" -ForegroundColor Cyan

Write-Host "[3/4] Open windows ..." -ForegroundColor Cyan
$opens = @(
    @{ Name = "browser (S4 first screen)"; Cmd = { Start-Process "$base/index.html#case=INV-V07&tab=summary" } },
    @{ Name = "explorer: submission package"; Cmd = { Start-Process explorer.exe $pkg } },
    @{ Name = "explorer: slides"; Cmd = { Start-Process explorer.exe $slides } }
)
if ($DryRun) {
    foreach ($o in $opens) { Write-Host "      [dry-run] would open: $($o.Name)" }
} else {
    foreach ($o in $opens) { & $o.Cmd; Write-Host "      opened: $($o.Name)" }
    Start-Sleep -Milliseconds 600
}

Write-Host ""
Write-Host "[4/4] Deep links (paste into the address bar, in order):" -ForegroundColor Cyan
$links = @(
    @("S4", "#case=INV-V07&tab=summary"),
    @("S4", "#case=INV-V07&tab=timeline"),
    @("S5", "#case=INV-V08&tab=summary"),
    @("S5", "#case=INV-V08&tab=timeline"),
    @("S6", "#case=INV-V04&tab=sources")
)
foreach ($l in $links) { Write-Host ("      {0}  {1}/index.html{2}" -f $l[0], $base, $l[1]) }

Write-Host ""
Write-Host "Shot order (9 segments, one file each):" -ForegroundColor Cyan
Write-Host "      S1 s1.png | S2 s2.png | S3 s3.png | S4 INV-V07 | S5 INV-V08 | S6 INV-V04 | S7 package dir | S8 terminal | S9 s6.png"

Write-Host ""
Write-Host "Terminal command for S8 (run live):" -ForegroundColor Cyan
Write-Host "      cd `"$root`""
Write-Host "      python scripts/verify.py --with-rubric"

Write-Host ""
Write-Host "Before recording: 1920x1080 / 100% scale / notifications off / mouse highlight on." -ForegroundColor Yellow
Write-Host "Stop server after recording: Get-NetTCPConnection -LocalPort $Port -State Listen | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force }" -ForegroundColor DarkGray
