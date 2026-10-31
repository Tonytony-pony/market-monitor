"""Discord の Webhook にサマリー（①②）とレポートのリンク・HTMLファイルを送る。

環境変数: DISCORD_WEBHOOK_URL（必須）、PAGES_URL（GitHub Pages のURL。末尾の / は無くてよい）
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MAX_ATTACH = 9_500_000  # Discord の添付上限 10MB に余裕を持たせる
LEADING_NO = re.compile(r"^[①-⑳]\s*")


def numbered(items: list[str]) -> str:
    return "\n".join(f"{i}. {LEADING_NO.sub('', t)}" for i, t in enumerate(items or [], start=1))


def market_lines(market: dict) -> str:
    lines = []
    for r in market["instruments"]:
        if r.get("missing"):
            continue
        if r["id"] in ("jgb10y", "ust10y"):
            chg = f"{r['change_abs'] * 100:+.1f}bp"
            close = f"{r['close']:.3f}%"
        else:
            chg = f"{r['change']:+.2f}%"
            close = f"{r['close']:,.{r['decimals']}f}"
        lines.append(f"{r['name']} {close}（{chg}）")
    return "\n".join(lines)


def eval_embed(ev: dict) -> dict:
    """試運転期間中のルーチンの自己評価（run_eval.json）を Discord 用にまとめる。"""
    def joined(key):
        return "、".join(ev.get(key) or []) or "なし"

    lines = [
        f"検索 {ev.get('searches', '?')} 回 / 記事取得 成功 {ev.get('fetch_ok', '?')} 件",
        f"開けなかったサイト: {joined('fetch_failed_domains')}",
        f"薄くなった箇所: {joined('weak_sections')}",
        f"数字チェック NG: 初回 {ev.get('factcheck_first_ng', '?')} 件 → 最終 {ev.get('factcheck_final_ng', '?')} 件",
        f"許可リスト追加: **{ev.get('allowlist_needed', '?')}**（候補: {joined('allowlist_candidates')}）",
        "",
        str(ev.get("comment", "")),
    ]
    return {"title": "試運転の評価", "description": "\n".join(lines)[:4000], "color": 0x8E8E8E}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--message", help="レポートの代わりにこの文だけを送る（障害通知用）")
    args = ap.parse_args()
    webhook = os.environ["DISCORD_WEBHOOK_URL"]

    if args.message:
        requests.post(webhook, json={"content": args.message[:1900]}, timeout=30).raise_for_status()
        return 0

    d = ROOT / "data" / args.date
    analysis = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
    market = json.loads((d / "market.json").read_text(encoding="utf-8"))
    s = analysis.get("summary", {})
    pages = os.environ.get("PAGES_URL", "").rstrip("/")
    url = f"{pages}/{args.date}.html" if pages else None

    desc = (f"**① 米国株市場への影響を意識した直近の動き**\n{numbered(s.get('recent_moves'))}\n\n"
            f"**② 次の米国市場で見込まれる動き・注意点**\n{numbered(s.get('outlook'))}")
    embed = {
        "title": f"マーケット日報 {args.date}",
        "description": desc[:4000],
        "color": 0x173F66,
        "fields": [{"name": "主要指標", "value": market_lines(market)[:1024]}],
    }
    if url:
        embed["url"] = url
    embeds = [embed]
    eval_path = d / "run_eval.json"
    if eval_path.exists():
        embeds.append(eval_embed(json.loads(eval_path.read_text(encoding="utf-8"))))
    payload = {"content": f"**{s.get('headline', '')}**" + (f"\n{url}" if url else ""), "embeds": embeds}

    report = ROOT / "reports" / f"{args.date}.html"
    files = {}
    if report.exists() and report.stat().st_size <= MAX_ATTACH:
        files["files[0]"] = (report.name, report.read_bytes(), "text/html")
    if files:
        r = requests.post(webhook, data={"payload_json": json.dumps(payload, ensure_ascii=False)}, files=files,
                          timeout=60)
    else:
        r = requests.post(webhook, json=payload, timeout=60)
    if r.status_code >= 300:
        print(r.status_code, r.text, file=sys.stderr)
        return 1
    print("sent", "with attachment" if files else "without attachment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
