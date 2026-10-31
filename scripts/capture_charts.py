"""TradingView の日足チャート（直近1年）を撮影して data/<date>/charts/<id>.png に保存する。

- TradingView に無い銘柄（日経VI）は、日経公式CSVの履歴を Lightweight Charts で描いて撮影する。
- 埋め込みウィジェットは東証銘柄を表示できないため、チャートページそのものを開いて撮影する。
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = {"width": 1280, "height": 760}

HIDE_CSS = """
[class*="sellBuyAndPresetsButtonsContainer"],
[class*="toast"], [data-role="toast-container"], [class*="popup"] { display: none !important; }
"""

LWC_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>body{margin:0;background:#fff;font-family:sans-serif}#t{padding:10px 14px;font-size:15px;color:#131722}</style>
</head><body><div id="w" style="width:1100px"><div id="t"></div><div id="c" style="width:1100px;height:560px"></div></div><script>
const d = __DATA__;
document.getElementById('t').textContent = d.title;
const chart = LightweightCharts.createChart(document.getElementById('c'), {
  width: 1100, height: 560, layout: {background: {color: '#ffffff'}, textColor: '#131722'},
  grid: {vertLines: {color: '#f0f3fa'}, horzLines: {color: '#f0f3fa'}},
  timeScale: {borderColor: '#d1d4dc'}, rightPriceScale: {borderColor: '#d1d4dc'}});
const s = chart.addCandlestickSeries({upColor: '#089981', downColor: '#f23645', borderVisible: false,
  wickUpColor: '#089981', wickDownColor: '#f23645'});
s.setData(d.bars);
chart.timeScale().fitContent();
window.__done = true;
</script></body></html>"""


def capture_tradingview(page, symbol: str, path: Path) -> None:
    page.goto(f"https://jp.tradingview.com/chart/?symbol={symbol}&interval=D", wait_until="domcontentloaded")
    page.wait_for_selector(".layout__area--center canvas", timeout=60000)
    page.wait_for_timeout(4000)
    page.get_by_text("1年", exact=True).first.click()
    page.wait_for_timeout(3500)
    page.add_style_tag(content=HIDE_CSS)
    page.mouse.move(5, 5)  # 十字カーソルの表示を避ける
    page.locator(".layout__area--center").screenshot(path=str(path), type="png")


def capture_history(page, title: str, bars: list, path: Path) -> None:
    page.set_content(LWC_PAGE.replace("__DATA__", json.dumps({"title": title, "bars": bars}, ensure_ascii=False)))
    page.wait_for_function("window.__done === true", timeout=30000)
    page.wait_for_timeout(1000)
    page.locator("#w").screenshot(path=str(path), type="png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD（data/<date>/ に保存）")
    ap.add_argument("--only", nargs="*", help="撮影する銘柄IDを絞る")
    args = ap.parse_args()

    instruments = json.loads((ROOT / "config" / "instruments.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "data" / args.date / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    market_path = ROOT / "data" / args.date / "market.json"
    market = json.loads(market_path.read_text(encoding="utf-8")) if market_path.exists() else {}

    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, locale="ja-JP", timezone_id="Asia/Tokyo")
        page = ctx.new_page()
        for ins in instruments:
            if args.only and ins["id"] not in args.only:
                continue
            path = out_dir / f"{ins['id']}.png"
            try:
                if ins["tv"]:
                    capture_tradingview(page, ins["tv"], path)
                else:
                    bars = market.get("history", {}).get(ins["id"], [])
                    if not bars:
                        raise RuntimeError("履歴データが無い（先に fetch_data.py を実行）")
                    # TradingView のページはCSPでスクリプト実行を禁じているので、別タブで描く
                    blank = ctx.new_page()
                    capture_history(blank, f"{ins['name']} · 日足（日経公式データより描画）", bars, path)
                    blank.close()
                print(f"ok  {ins['id']}")
            except Exception as e:  # 1銘柄の失敗で全体を止めない
                failed.append(ins["id"])
                print(f"NG  {ins['id']}: {e}", file=sys.stderr)
        browser.close()

    (out_dir / "_status.json").write_text(json.dumps({"failed": failed}, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
