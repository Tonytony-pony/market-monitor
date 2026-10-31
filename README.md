# マーケット日報（毎日の市場環境モニタリング）

日経平均・JPX日経400・グロース250・日経先物・日経VI・ドル円・NYダウ・ナスダック・S&P500・ビットコイン・原油・金・プラチナ・日米10年債を、
**米国株市場への影響**という観点で毎朝まとめ、GitHub Pages と Discord に届ける。

## 流れ（日本時間 火〜土）

| 時刻 | 担当 | 内容 |
| --- | --- | --- |
| 6:20 | GitHub Actions `collect` | 数値取得（`scripts/fetch_data.py`）と TradingView 日足チャート撮影（`scripts/capture_charts.py`）→ `data/<日付>/` に commit |
| 6:40 | Claude Code ルーチン | `ROUTINE.md` に沿って Web 調査・分析 → `analysis.json` → 数字チェック（`scripts/factcheck.py`）→ HTML（`scripts/render_report.py`）→ push |
| push 直後 | GitHub Actions `publish` | GitHub Pages を更新し、Discord にサマリーと HTML を送信（`scripts/notify_discord.py`） |

- 監視銘柄は `config/instruments.json`。
- 分析の指示を変えたいときは `ROUTINE.md` を編集する（ルーチン自体の設定は変えなくてよい）。
- 米国の夏時間（3月〜11月）は米国株の終値が1時間早く出るので、cron を1時間早めれば6時台前半に届く。

## 必要な設定

- リポジトリの Secrets に `DISCORD_WEBHOOK_URL`
- Settings → Pages → Source を「GitHub Actions」
