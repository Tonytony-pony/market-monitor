"""撮影専用のブラウザで TradingView にログインしておくための補助スクリプト（最初に1回だけ実行）。

ブラウザが開くので、自分で TradingView にログインし、日報用レイアウトが表示されることを確かめてから
ブラウザを閉じる。ログイン状態は --profile のフォルダに残り、毎朝の撮影で使われる。
"""
import argparse

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--layout", default="")
    args = ap.parse_args()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(args.profile, headless=False, no_viewport=True, locale="ja-JP")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"https://jp.tradingview.com/chart/{args.layout + '/' if args.layout else ''}")
        print("ブラウザで TradingView にログインし、日報用レイアウトが表示されたらブラウザを閉じてください。")
        page.wait_for_event("close", timeout=0)
        ctx.close()


if __name__ == "__main__":
    main()
