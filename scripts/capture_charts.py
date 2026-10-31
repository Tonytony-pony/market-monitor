"""TradingView の日足チャート（直近1年）を撮影して data/<date>/charts/<id>.png に保存する。

- 埋め込みウィジェットは東証銘柄を表示できないため、チャートページそのものを開いて撮影する。
- TradingView に無い銘柄（日経VI）は撮影しない（レポートでは数値のみ）。
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


def capture_tradingview(page, symbol: str, path: Path) -> None:
    page.goto(f"https://jp.tradingview.com/chart/?symbol={symbol}&interval=D", wait_until="domcontentloaded")
    page.wait_for_selector(".layout__area--center canvas", timeout=60000)
    page.wait_for_timeout(4000)
    page.get_by_text("1年", exact=True).first.click()
    page.wait_for_timeout(3500)
    page.add_style_tag(content=HIDE_CSS)
    page.mouse.move(5, 5)  # 十字カーソルの表示を避ける
    page.locator(".layout__area--center").screenshot(path=str(path), type="png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD（data/<date>/ に保存）")
    ap.add_argument("--only", nargs="*", help="撮影する銘柄IDを絞る")
    args = ap.parse_args()

    instruments = json.loads((ROOT / "config" / "instruments.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "data" / args.date / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, locale="ja-JP", timezone_id="Asia/Tokyo")
        page = ctx.new_page()
        for ins in instruments:
            if not ins["tv"] or args.only and ins["id"] not in args.only:
                continue
            try:
                capture_tradingview(page, ins["tv"], out_dir / f"{ins['id']}.png")
                print(f"ok  {ins['id']}")
            except Exception as e:  # 1銘柄の失敗で全体を止めない
                failed.append(ins["id"])
                print(f"NG  {ins['id']}: {e}", file=sys.stderr)
        browser.close()

    (out_dir / "_status.json").write_text(json.dumps({"failed": failed}, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
