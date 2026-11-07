"""analysis.json の本文に出てくる数字を market.json（と出典付きの external_facts）と突き合わせる。

照合できない数字・符号が逆の数字を data/<date>/factcheck.json に書き出し、1件でもあれば終了コード1を返す。
ルーチンはこれが0になるまで本文を直す。
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NUM_RE = re.compile(
    r"(約|およそ)?([+\-−▲△]?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"\s*(%|％|円|銭|ドル|ポイント|pt|bp|bps|ベーシスポイント)?"
)
# 単位の無い数字のうち、直後がこれなら日付・期間・回数などとみなして照合しない
SKIP_NEXT = ("年", "月", "日", "時", "分", "週", "期", "回", "倍", "人", "社", "件", "位", "カ月", "ヶ月", "か月",
             "営業日", "銘柄", "本", "つ", "番", "Q", "名", "億", "兆", "万")
SIGNED_FIELDS = {"change", "change_abs", "Perf.W", "Perf.1M", "Perf.YTD", "bp", "vs_sma50", "vs_sma200", "vs_52wh"}
TEXT_FIELDS = ("headline", "analysis", "us_impact")
SECTOR_TEXT_FIELDS = ("headline", "analysis", "rotation", "outlook")
NEWS_TEXT_FIELDS = ("title", "what", "why", "watch")


def candidates(market: dict, analysis: dict) -> list[tuple[float, bool, str]]:
    out = []
    for r in market["instruments"]:
        if r.get("missing"):
            continue
        name = r["name"]
        for k in ("close", "open", "high", "low", "change", "change_abs", "Perf.W", "Perf.1M", "Perf.YTD",
                  "SMA50", "SMA200", "RSI", "price_52_week_high", "price_52_week_low"):
            if r.get(k) is not None:
                out.append((r[k], k in SIGNED_FIELDS, f"{name}.{k}"))
        close = r.get("close")
        if r["id"] in ("jgb10y", "ust10y") and r.get("change_abs") is not None:
            out.append((r["change_abs"] * 100, True, f"{name}.bp"))
        for k, label in (("SMA50", "vs_sma50"), ("SMA200", "vs_sma200"), ("price_52_week_high", "vs_52wh")):
            if close and r.get(k):
                out.append(((close / r[k] - 1) * 100, True, f"{name}.{label}"))
        if r.get("check"):
            out.append((r["check"]["value"], False, f"{name}.check"))
    for s in market.get("sectors", []):
        for k in ("close", "change", "Perf.W", "Perf.1M", "Perf.YTD", "vs_spy"):
            if s.get(k) is not None:
                out.append((s[k], k != "close", f"セクター{s['name']}.{k}"))
    for i, f in enumerate(analysis.get("external_facts", [])):
        for m in NUM_RE.finditer(str(f.get("value", ""))):
            v = float(m.group(3).replace(",", "") + ("." + m.group(4) if m.group(4) else ""))
            sign = -1 if m.group(2) in ("-", "−", "▲") else 1
            out.append((sign * v, bool(m.group(2)), f"external_facts[{i}]"))
    return out


def iter_texts(analysis: dict):
    s = analysis.get("summary", {})
    for k in ("headline", "recent_moves", "outlook", "watch_points"):
        v = s.get(k)
        for j, t in enumerate(v if isinstance(v, list) else [v]):
            if t:
                yield f"summary.{k}[{j}]", t
    for j, ev in enumerate(s.get("events", [])):
        yield f"summary.events[{j}]", ev.get("event", "")
    sec = analysis.get("sectors", {})
    for k in SECTOR_TEXT_FIELDS:
        if sec.get(k):
            yield f"sectors.{k}", sec[k]
    tn = analysis.get("top_news") or {}
    if tn.get("headline"):
        yield "top_news.headline", tn["headline"]
    for j, it in enumerate(tn.get("items") or []):
        for k in NEWS_TEXT_FIELDS:
            if it.get(k):
                yield f"top_news.items[{j}].{k}", it[k]
    for iid, body in analysis.get("instruments", {}).items():
        for k in TEXT_FIELDS:
            if body.get(k):
                yield f"instruments.{iid}.{k}", body[k]


def check_text(text: str, cands) -> list[dict]:
    issues = []
    for m in NUM_RE.finditer(text):
        approx, sign, intpart, dec, unit = m.groups()
        before = text[max(0, m.start() - 1):m.start()]
        after = text[m.end():m.end() + 3]
        if before and (before.isascii() and before.isalpha() or before in "&第:/／"):
            continue  # S&P500・Q3・第3四半期・時刻・日付
        if after[:1] in (":", "/", "／") or after[:1].isascii() and after[:1].isalpha() and not unit:
            continue
        if not unit:
            if "," not in intpart and dec is None:
                continue  # 単位の無い素の整数は文脈依存なので照合しない
            if after.startswith(SKIP_NEXT):
                continue
        if unit == "ドル" and intpart == "1" and dec is None:
            continue  # 「1ドル=157円」の1
        v = float(intpart.replace(",", "") + ("." + dec if dec else ""))
        tol = 0.5 * 10 ** -(len(dec) if dec else 0) + 1e-9
        hits = []
        for c, signed, label in cands:
            t = max(tol, abs(c) * 0.01) if approx else tol
            if abs(abs(c) - v) <= t + abs(c) * 1e-6:
                hits.append((c, signed, label))
        snippet = text[max(0, m.start() - 18):m.end() + 6].replace("\n", " ")
        if not hits:
            issues.append({"number": m.group(0), "snippet": snippet, "problem": "データに無い数字"})
            continue
        if sign:
            neg = sign in ("-", "−", "▲")
            signed_hits = [h for h in hits if h[1]]
            if signed_hits and len(signed_hits) == len(hits) and all((h[0] < 0) != neg for h in signed_hits):
                issues.append({"number": m.group(0), "snippet": snippet,
                               "problem": f"符号が逆（データ: {signed_hits[0][2]} = {signed_hits[0][0]:+.4g}）"})
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    d = ROOT / "data" / args.date
    market = json.loads((d / "market.json").read_text(encoding="utf-8"))
    analysis = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
    cands = candidates(market, analysis)

    issues, checked = [], 0
    for path, text in iter_texts(analysis):
        checked += len(NUM_RE.findall(text))
        for it in check_text(text, cands):
            issues.append({"field": path, **it})

    fact_warnings = [f"external_facts[{i}] の出典が2件未満: {f.get('label', '')}"
                     for i, f in enumerate(analysis.get("external_facts", []))
                     if len([u for u in f.get("sources", []) if u]) < 2]

    result = {"issues": issues, "fact_warnings": fact_warnings,
              "data_warnings": market.get("warnings", []), "numbers_scanned": checked}
    (d / "factcheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in issues:
        print(f"NG {it['field']}: {it['number']} … {it['problem']} 「{it['snippet']}」")
    for w in fact_warnings:
        print("WARN", w)
    print(f"{len(issues)} issues / {len(fact_warnings)} source warnings")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
