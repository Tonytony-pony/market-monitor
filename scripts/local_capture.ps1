# Daily job on the user's PC: market numbers (market.json) + TradingView charts with the user's own layout
# (data/<date>/charts_custom) -> push. GitHub's scheduled workflows start late or not at all, so this is the main path.
# Run by Windows Task Scheduler (Tue-Sat 06:20 JST). Settings come from config/local.json (not committed).
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
New-Item -ItemType Directory -Force logs | Out-Null
$D = (Get-Date).ToString('yyyy-MM-dd')
Start-Transcript -Path "logs\capture-$D.log" -Append | Out-Null

$cfg = Get-Content config\local.json -Raw -Encoding UTF8 | ConvertFrom-Json
git pull --rebase --autostash -q
& .venv\Scripts\python.exe scripts\fetch_data.py --date $D
if ($LASTEXITCODE -ne 0) { Write-Output "fetch failed: $LASTEXITCODE" }
& .venv\Scripts\python.exe scripts\capture_charts.py --date $D --out charts_custom --profile $cfg.profile --layout $cfg.layout
if ($LASTEXITCODE -ne 0) { Write-Output "capture failed: $LASTEXITCODE"; Stop-Transcript | Out-Null; exit 1 }

foreach ($p in "data/$D/market.json", "data/$D/charts_custom") { if (Test-Path $p) { git add $p } }
git commit -q -m "data + charts(custom): $D"
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
