"""各銘柄の数値を取得して data/<date>/market.json に保存する。ここで取った数値をレポートの「正」とする。

- 主データ: TradingView の scanner API（チャートと同じデータ）
- 日経平均・日経VI: 日経公式CSV（日経VIは TradingView に無いため主データにもなる）
- 照合用: yfinance（取得元の違う数値と比べ、大きくずれていれば警告を付ける）
"""
import argparse
import csv
import io
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0"}

SCAN_COLUMNS = [
    "close", "change", "change_abs", "open", "high", "low",
    "Perf.W", "Perf.1M", "Perf.YTD", "SMA50", "SMA200", "RSI",
    "price_52_week_high", "price_52_week_low",
]
NIKKEI_CSV = {
    "nikkei225": "https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_daily_jp.csv",
    "nikkei_vi": "https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_vi_daily_jp.csv",
}


def fetch_scanner(tickers: list[str]) -> dict[str, dict]:
    r = requests.post(
        "https://scanner.tradingview.com/global/scan",
        json={"symbols": {"tickers": tickers}, "columns": SCAN_COLUMNS},
        headers=UA, timeout=30,
    )
    r.raise_for_status()
    return {row["s"]: dict(zip(SCAN_COLUMNS, row["d"])) for row in r.json()["data"]}


def fetch_nikkei_csv(url: str) -> list[dict]:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    rows = []
    for rec in csv.reader(io.StringIO(r.content.decode("shift_jis", errors="replace"))):
        if len(rec) != 5 or not rec[0][:4].isdigit():
            continue  # ヘッダーと末尾の注記を除く
        d, close, open_, high, low = rec
        rows.append({"time": d.replace("/", "-"), "open": float(open_), "high": float(high),
                     "low": float(low), "close": float(close)})
    return rows


def quote_from_bars(bars: list[dict]) -> dict:
    last, prev = bars[-1], bars[-2]
    year_ago = (date.fromisoformat(last["time"]) - timedelta(days=365)).isoformat()
    year = [b for b in bars if b["time"] >= year_ago]
    return {
        "close": last["close"], "open": last["open"], "high": last["high"], "low": last["low"],
        "change_abs": last["close"] - prev["close"],
        "change": (last["close"] / prev["close"] - 1) * 100,
        "price_52_week_high": max(b["high"] for b in year),
        "price_52_week_low": min(b["low"] for b in year),
        "as_of": last["time"],
    }


def fetch_yfinance(keys: list[str]) -> dict[str, dict]:
    import warnings

    import yfinance as yf

    warnings.filterwarnings("ignore")  # pandas の非推奨警告がログを埋めるため
    out = {}
    for key in keys:
        try:
            hist = yf.Ticker(key).history(period="7d", interval="1d")
            if len(hist) >= 1:
                out[key] = {"close": float(hist["Close"].iloc[-1]), "as_of": hist.index[-1].strftime("%Y-%m-%d")}
        except Exception as e:
            print(f"yfinance {key}: {e}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(JST).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    instruments = json.loads((ROOT / "config" / "instruments.json").read_text(encoding="utf-8"))
    scan = fetch_scanner([i["quote"] for i in instruments if i["quote"]])
    nikkei = {k: fetch_nikkei_csv(u) for k, u in NIKKEI_CSV.items()}
    yf_data = fetch_yfinance([i["check"]["key"] for i in instruments
                              if i["check"] and i["check"]["source"] == "yfinance"])

    rows, warnings = [], []
    for ins in instruments:
        if ins["quote"]:
            q = scan.get(ins["quote"])
            source = f"TradingView {ins['quote']}"
            if q and ins["id"] in nikkei:
                # 公式値がある指数は四本値・前日比を公式CSVで上書きする（テクニカル指標は TradingView のまま）
                q = {**q, **quote_from_bars(nikkei[ins["id"]])}
                source = f"日経公式CSV（指標は TradingView {ins['quote']}）"
        else:
            q = quote_from_bars(nikkei[ins["id"]])
            source = "日経公式CSV"
        if not q or q.get("close") is None:
            warnings.append(f"{ins['name']}: 数値を取得できなかった")
            rows.append({"id": ins["id"], "name": ins["name"], "group": ins["group"], "missing": True})
            continue

        check = None
        if ins["check"]:
            c = ins["check"]
            if c["source"] == "nikkei_csv":
                ref = {"close": nikkei[c["key"]][-1]["close"], "as_of": nikkei[c["key"]][-1]["time"]}
                tol = 0.05
            else:
                ref = yf_data.get(c["key"])
                tol = c["tol"]
            if ref:
                diff = (q["close"] / ref["close"] - 1) * 100
                status = "ok" if abs(diff) <= tol else "mismatch"
                check = {"source": c["source"], "key": c["key"], "value": ref["close"], "as_of": ref["as_of"],
                         "diff_pct": round(diff, 3), "tolerance_pct": tol, "status": status}
                if status != "ok":
                    warnings.append(f"{ins['name']}: 主データ {q['close']} と照合用 {ref['close']}"
                                    f"（{c['key']}）が {diff:+.2f}% ずれている")

        rows.append({
            "id": ins["id"], "name": ins["name"], "group": ins["group"], "decimals": ins["decimals"],
            "tv_symbol": ins["tv"], "source": source,
            **{k: q.get(k) for k in SCAN_COLUMNS},
            "as_of": q.get("as_of"),
            "check": check,
        })

    year_ago = (date.fromisoformat(args.date) - timedelta(days=372)).isoformat()
    out = {
        "report_date": args.date,
        "fetched_at": datetime.now(JST).isoformat(timespec="seconds"),
        "instruments": rows,
        "warnings": warnings,
        "history": {"nikkei_vi": [b for b in nikkei["nikkei_vi"] if b["time"] >= year_ago]},
    }
    path = ROOT / "data" / args.date / "market.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {path} ({len(rows)} instruments, {len(warnings)} warnings)")
    for w in warnings:
        print("WARN", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
