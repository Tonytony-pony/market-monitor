# Daily capture on the user's PC: TradingView charts with the user's own layout -> data/<date>/charts_custom -> push.
# Run by Windows Task Scheduler (Tue-Sat 06:20 JST). Settings come from config/local.json (not committed).
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
New-Item -ItemType Directory -Force logs | Out-Null
$D = (Get-Date).ToString('yyyy-MM-dd')
Start-Transcript -Path "logs\capture-$D.log" -Append | Out-Null

$cfg = Get-Content config\local.json -Raw -Encoding UTF8 | ConvertFrom-Json
git pull --rebase --autostash -q
& .venv\Scripts\python.exe scripts\capture_charts.py --date $D --out charts_custom --profile $cfg.profile --layout $cfg.layout
if ($LASTEXITCODE -ne 0) { Write-Output "capture failed: $LASTEXITCODE"; Stop-Transcript | Out-Null; exit 1 }

git add "data/$D/charts_custom"
git commit -q -m "charts(custom): $D"
$pushed = $false
foreach ($i in 1..3) {
    git pull --rebase --autostash -q
    git push -q
    if ($LASTEXITCODE -eq 0) { $pushed = $true; break }
    Start-Sleep -Seconds 10
}
Write-Output "pushed: $pushed"
Stop-Transcript | Out-Null
if (-not $pushed) { exit 1 }
