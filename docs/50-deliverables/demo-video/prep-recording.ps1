# Recording prep for the 6-page / 3:30 PPT version.
# Keep ASCII-only: Windows PowerShell 5.1 reads .ps1 as ANSI.
# Usage:
#   powershell -ExecutionPolicy Bypass -File docs\50-deliverables\demo-video\prep-recording.ps1
#   ... prep-recording.ps1 -DryRun        # print only, open nothing
#   ... prep-recording.ps1 -WithWebUI     # also start WebUI (optional 30s supplement)
param(
    [int]$Port = 8000,
    [switch]$DryRun,
    [switch]$WithWebUI
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$pptx = Join-Path $scriptDir "presentation.pptx"
$pdf  = Join-Path $scriptDir "presentation.pdf"
$src  = Join-Path $scriptDir "narration-script-3m30-ppt.md"
$runbook = Join-Path $scriptDir "RECORDING-RUNBOOK.md"
$base = "http://127.0.0.1:$Port"

foreach ($f in @($pptx, $src, $runbook)) {
    if (-not (Test-Path $f)) { Write-Host "[ERROR] missing: $f" -ForegroundColor Red; exit 1 }
}

Write-Host "[1/3] Open the main screen (PPT) ..." -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "      [dry-run] would open: presentation.pptx  (then press F5 for slideshow)"
    Write-Host "      [dry-run] would open: presentation.pdf   (backup)"
    Write-Host "      [dry-run] would open: narration-script-3m30-ppt.md"
} else {
    Start-Process $pptx
    Start-Sleep -Milliseconds 800
    Start-Process $pdf
    Start-Sleep -Milliseconds 400
    Start-Process $src
    Write-Host "      opened: PPT / PDF / script"
}

Write-Host "[2/3] Optional WebUI ..." -ForegroundColor Cyan
if ($WithWebUI) {
    function Test-Up { try { (Invoke-WebRequest -Uri "$base/index.html" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false } }
    if ($DryRun) {
        Write-Host "      [dry-run] would start: python -m http.server $Port --directory outputs/webui"
    } elseif (-not (Test-Up)) {
        Start-Process -FilePath "python" -ArgumentList "-m","http.server","$Port","--directory","outputs/webui" -WorkingDirectory $root -WindowStyle Hidden
        $i = 0; while ($i -lt 40 -and -not (Test-Up)) { Start-Sleep -Milliseconds 250; $i++ }
        if (Test-Up) { Write-Host "      WebUI ready: $base" -ForegroundColor Green }
        else { Write-Host "      [WARN] WebUI did not start" -ForegroundColor Yellow }
    } else { Write-Host "      port $Port already serving" -ForegroundColor Yellow }
    Write-Host "      supplement: $base/index.html#case=INV-V07&tab=summary"
    Write-Host "      supplement: $base/index.html#case=INV-V07&tab=timeline"
} else {
    Write-Host "      skipped (add -WithWebUI for the optional 30s supplement)"
}

Write-Host "[3/3] Shot card (6 segments, one file each):" -ForegroundColor Cyan
$shots = @(
    @("P1", "0:00-0:20", "cover, mouse still"),
    @("P2", "0:20-0:55", "left card -> right card"),
    @("P3", "0:55-1:35", "kernel -> first-fault -> LLM box"),
    @("P4", "1:35-2:25", "B-05 -> B-08..B-10 -> 70 -> 20"),
    @("P5", "2:25-3:00", "tests / train / valid rows"),
    @("P6", "3:00-3:30", "four boundaries -> bottom line")
)
foreach ($s in $shots) { Write-Host ("      {0}  {1}  {2}" -f $s[0], $s[1], $s[2]) }

Write-Host ""
Write-Host "Script:  $src" -ForegroundColor Cyan
Write-Host "Runbook: $runbook" -ForegroundColor Cyan
Write-Host ""
Write-Host "Before recording: 1920x1080 / 100% scale / notifications off / mouse highlight on / F5 slideshow." -ForegroundColor Yellow
Write-Host "After recording, stop WebUI: Get-NetTCPConnection -LocalPort $Port -State Listen | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force }" -ForegroundColor DarkGray
