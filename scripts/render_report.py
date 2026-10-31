"""market.json・analysis.json・factcheck.json・チャート画像から、1ファイルで完結するHTMLレポートを作る。

出力: reports/<date>.html（画像は埋め込み）と reports/index.html（過去分の一覧）
"""
import argparse
import base64
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOND_IDS = {"jgb10y", "ust10y"}
WEEKDAYS = "月火水木金土日"
LEADING_NO = re.compile(r"^[①-⑳]\s*")

CSS = """
:root{--ink:#1a1a1a;--ink-2:#555555;--ink-3:#8e8e8e;--accent:#173f66;--accent-tint:#eef3f8;
--hairline:#d9d9d9;--fill-gray:#e7e9ec;--paper:#ffffff;--neg:#a33c2e}
html{color-scheme:light}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Helvetica Neue",Arial,"Hiragino Kaku Gothic ProN","Hiragino Sans","Yu Gothic Medium","Yu Gothic",Meiryo,sans-serif;
font-size:15px;line-height:1.9;border-top:6px solid var(--accent);-webkit-font-smoothing:antialiased}
.page{max-width:880px;margin:0 auto;padding:56px clamp(16px,5vw,48px) 96px}
.doc-header{padding-bottom:28px;border-bottom:1px solid var(--ink)}
.eyebrow{font-size:11px;letter-spacing:.16em;color:var(--ink-3);text-transform:uppercase;margin:0 0 20px}
h1{font-size:25px;line-height:1.55;letter-spacing:.02em;margin:0 0 12px;font-feature-settings:"palt" 1}
.lead{font-size:14px;color:var(--ink-2);margin:0 0 24px;max-width:42em}
.doc-meta{font-size:12px;color:var(--ink-3);display:flex;gap:24px;flex-wrap:wrap}
.page>section{border-top:1px solid var(--hairline);padding-top:44px;margin-top:64px}
.page>section:first-of-type{border-top:0;padding-top:0;margin-top:56px}
h2{font-size:19px;letter-spacing:.03em;margin:0;font-feature-settings:"palt" 1}
h2 .no{color:var(--accent);margin-right:14px;font-variant-numeric:tabular-nums}
.msg{font-size:16px;font-weight:600;line-height:1.8;margin:18px 0 20px;max-width:40em}
h3{font-size:15px;margin:32px 0 8px}
h3 .lvl{font-size:12px;font-weight:600;color:var(--ink-3);margin-left:10px}
h3 .lvl b{color:var(--accent)}
p{margin:0 0 16px;max-width:42em}
.summary{list-style:none;margin:16px 0 0;padding:0;counter-reset:s;max-width:44em}
.summary li{counter-increment:s;position:relative;padding-left:2.4em;margin-bottom:14px}
.summary li::before{content:counter(s,decimal-leading-zero);position:absolute;left:0;top:.4em;
font-size:12px;font-weight:700;color:var(--accent);letter-spacing:.04em;font-variant-numeric:tabular-nums}
ul{margin:0 0 16px;max-width:41em;list-style:none;padding-left:1.2em}
li{margin-bottom:6px}
ul li::before{content:"–";float:left;margin-left:-1.2em;color:var(--ink-3)}
.kpis{display:flex;flex-wrap:wrap;row-gap:16px;margin:8px 0 8px}
.kpi{padding:2px 28px}
.kpi:first-child{padding-left:0}
.kpi+.kpi{border-left:1px solid var(--hairline)}
.kpi .v{font-size:24px;font-weight:700;color:var(--accent);line-height:1.3;font-variant-numeric:tabular-nums}
.kpi .v.neg{color:var(--neg)}
.kpi .v small{font-size:13px;font-weight:600;margin-left:2px}
.kpi .l{font-size:11.5px;color:var(--ink-3);letter-spacing:.06em;margin-top:4px}
.tbl{overflow-x:auto}
table{width:100%;border-collapse:collapse;margin:24px 0 8px;font-size:13px;line-height:1.6}
caption{text-align:left;font-size:12.5px;font-weight:600;margin-bottom:10px}
th{font-size:12px;font-weight:600;text-align:left;padding:9px 10px;white-space:nowrap;
border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);vertical-align:bottom}
td{padding:9px 10px;border-bottom:1px solid var(--hairline);vertical-align:top}
th.num,td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.neg{color:var(--neg)}
td.lvl-大{color:var(--accent);font-weight:700}
figure{margin:24px 0 8px}
figcaption{font-size:12.5px;font-weight:600;margin-bottom:10px}
figure img{width:100%;height:auto;display:block;border-bottom:1px solid var(--hairline)}
.src{font-size:11.5px;color:var(--ink-3);margin:6px 0 0;max-width:none}
.src a{color:var(--ink-3)}
.note{font-size:12.5px;color:var(--ink-2);border-left:2px solid var(--hairline);padding:2px 0 2px 14px;margin:20px 0 16px;max-width:40em}
.em{color:var(--accent);font-weight:700}
a{color:inherit;text-decoration:underline;text-decoration-color:var(--hairline);text-underline-offset:3px}
a:hover{text-decoration-color:var(--accent)}
.doc-footer{margin-top:88px;padding-top:20px;border-top:1px solid var(--hairline);
font-size:11.5px;color:var(--ink-3);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
@media print{@page{size:A4;margin:16mm}body{border-top-width:4px}.page{max-width:none;padding:0}
.page>section{margin-top:48px;padding-top:32px}table,figure,.kpis{break-inside:avoid}a{text-decoration:none}}
"""


def esc(s) -> str:
    return html.escape(str(s or ""))


def paras(text: str) -> str:
    blocks = [b.strip() for b in str(text or "").split("\n") if b.strip()]
    return "".join(f"<p>{esc(b)}</p>" for b in blocks)


def fmt(v, decimals: int) -> str:
    return "–" if v is None else f"{v:,.{decimals}f}"


def fmt_signed(v, decimals: int, suffix: str = "") -> tuple[str, bool]:
    if v is None:
        return "–", False
    return (f"+{v:,.{decimals}f}{suffix}" if v >= 0 else f"−{abs(v):,.{decimals}f}{suffix}"), v < 0


def jp_date(iso: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{d.year}年{d.month}月{d.day}日（{WEEKDAYS[d.weekday()]}）"


def change_cells(r: dict) -> tuple[tuple[str, bool], tuple[str, bool]]:
    """（前日比, 騰落率）。金利は騰落率の代わりに bp を出す。"""
    dec = r["decimals"]
    if r["id"] in BOND_IDS:
        bp = None if r.get("change_abs") is None else r["change_abs"] * 100
        return fmt_signed(r.get("change_abs"), 3, "%pt"), fmt_signed(bp, 1, "bp")
    return fmt_signed(r.get("change_abs"), dec), fmt_signed(r.get("change"), 2, "%")


def img_tag(path: Path, alt: str) -> str:
    if not path.exists():
        return '<p class="note">チャートを取得できなかった。</p>'
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{esc(alt)}">'


def overview_table(rows: list[dict], analysis: dict) -> str:
    body = []
    for r in rows:
        a = analysis.get("instruments", {}).get(r["id"], {})
        lvl = a.get("us_impact_level", "–")
        if r.get("missing"):
            body.append(f'<tr><td>{esc(r["name"])}</td><td class="num" colspan="5">取得失敗</td><td>{esc(lvl)}</td></tr>')
            continue
        (chg, neg1), (pct, neg2) = change_cells(r)
        w, negw = fmt_signed(r.get("Perf.W"), 2, "%")
        m, negm = fmt_signed(r.get("Perf.1M"), 2, "%")
        unit = "%" if r["id"] in BOND_IDS else ""
        body.append(
            f'<tr><td><a href="#{r["id"]}">{esc(r["name"])}</a></td>'
            f'<td class="num">{fmt(r["close"], r["decimals"])}{unit}</td>'
            f'<td class="num{" neg" if neg1 else ""}">{chg}</td>'
            f'<td class="num{" neg" if neg2 else ""}">{pct}</td>'
            f'<td class="num{" neg" if negw else ""}">{w}</td>'
            f'<td class="num{" neg" if negm else ""}">{m}</td>'
            f'<td class="lvl-{esc(lvl)}">{esc(lvl)}</td></tr>')
    return ('<div class="tbl"><table><caption>図表1　主要指標の一覧（前日比・騰落率は直近の取引日ベース）</caption>'
            '<thead><tr><th>項目</th><th class="num">終値</th><th class="num">前日比</th><th class="num">騰落率</th>'
            '<th class="num">1週間</th><th class="num">1ヶ月</th><th>米株への影響</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            '<p class="src">出所: TradingView（日経平均・日経VIは日経公式データ）。金利の騰落率欄は前日比の変化幅（bp）。</p>')


def instrument_section(no: int, r: dict, a: dict, chart_dir: Path, fig_no: int) -> str:
    sid, name = r["id"], r["name"]
    if r.get("missing"):
        return (f'<section id="{sid}"><h2><span class="no">{no:02d}</span>{esc(name)}</h2>'
                f'<p class="note">数値を取得できなかったため、この項目は分析していない。</p></section>')
    (chg, neg1), (pct, neg2) = change_cells(r)
    unit = "%" if sid in BOND_IDS else ""
    kpis = [(fmt(r["close"], r["decimals"]) + unit, "終値", False), (chg, "前日比", neg1), (pct, "騰落率" if sid not in BOND_IDS else "変化幅", neg2)]
    if r.get("SMA200") and r.get("close"):
        v, n = fmt_signed((r["close"] / r["SMA200"] - 1) * 100, 1, "%")
        kpis.append((v, "200日線からの乖離", n))
    if r.get("RSI") is not None:
        kpis.append((f'{r["RSI"]:.0f}', "RSI(14)", False))
    kpi_html = "".join(f'<div class="kpi"><div class="v{" neg" if n else ""}">{esc(v)}</div><div class="l">{esc(l)}</div></div>'
                       for v, l, n in kpis)
    if r.get("tv_symbol"):
        chart_src = f'TradingView {esc(r["tv_symbol"])}'
        if sid == "wti":
            chart_src += "（チャートはWTI原油CFD、数値はNYMEX WTI先物の期近）"
        figure = (f'<figure><figcaption>図表{fig_no}　{esc(name)}　日足（直近1年）</figcaption>\n'
                  f'{img_tag(chart_dir / f"{sid}.png", name)}\n<p class="src">出所: {chart_src}</p></figure>')
    else:
        figure = f'<p class="src">出所: {esc(r.get("source"))}（{esc(r.get("as_of"))}時点）。チャートは掲載していない。</p>'
    sources = a.get("sources", [])
    src_links = " / ".join(f'<a href="{esc(s.get("url"))}">{esc(s.get("title") or s.get("url"))}</a>' for s in sources)
    lvl = a.get("us_impact_level", "–")
    return f"""<section id="{sid}">
<h2><span class="no">{no:02d}</span>{esc(name)}</h2>
<p class="msg">{esc(a.get("headline") or "分析なし")}</p>
<div class="kpis">{kpi_html}</div>
{figure}
<h3>動きと背景</h3>{paras(a.get("analysis"))}
<h3>米国株市場への影響<span class="lvl">影響度 <b>{esc(lvl)}</b></span></h3>{paras(a.get("us_impact"))}
{f'<p class="src">参考: {src_links}</p>' if src_links else ""}
</section>"""


def factcheck_section(no: int, rows: list[dict], fc: dict) -> str:
    trs = []
    for r in rows:
        c = r.get("check")
        if not c:
            continue
        status = "一致" if c["status"] == "ok" else "要確認"
        trs.append(f'<tr><td>{esc(r["name"])}</td><td class="num">{fmt(r["close"], r["decimals"])}</td>'
                   f'<td>{esc(c["source"])} {esc(c["key"])}</td><td class="num">{fmt(c["value"], r["decimals"])}</td>'
                   f'<td class="num">{c["diff_pct"]:+.2f}%</td><td>{status}</td></tr>')
    issues = fc.get("issues", [])
    warn = fc.get("data_warnings", []) + fc.get("fact_warnings", [])
    issue_html = ("".join(f'<li>{esc(i["field"])}: 「{esc(i["snippet"])}」 — {esc(i["problem"])}</li>' for i in issues)
                  if issues else "")
    msg = (f'本文中の数字 {fc.get("numbers_scanned", 0)} 個を取得データと照合し、不一致は {len(issues)} 件。'
           if fc else "本文の数字チェックは実行されていない。")
    return f"""<section id="factcheck">
<h2><span class="no">{no:02d}</span>数字のチェック結果</h2>
<p class="msg">{esc(msg)}</p>
{f"<ul>{issue_html}</ul>" if issue_html else ""}
{"".join(f'<p class="note">{esc(w)}</p>' for w in warn)}
<div class="tbl"><table><caption>主データと別の取得元との照合（ずれは許容範囲内なら「一致」）</caption>
<thead><tr><th>項目</th><th class="num">主データ</th><th>照合先</th><th class="num">照合値</th><th class="num">差</th><th>判定</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div>
<p class="src">金・プラチナ・原油・ビットコインは照合先が先物・取引所違いのため、数%以内の差を許容している。</p>
</section>"""


def render(date: str) -> Path:
    d = ROOT / "data" / date
    market = json.loads((d / "market.json").read_text(encoding="utf-8"))
    analysis = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
    fc_path = d / "factcheck.json"
    fc = json.loads(fc_path.read_text(encoding="utf-8")) if fc_path.exists() else {}
    rows = market["instruments"]
    s = analysis.get("summary", {})

    def ol(items):
        # 番号はCSSで付けるので、本文側の「①」などは外す
        return '<ol class="summary">' + "".join(f"<li>{esc(LEADING_NO.sub('', t))}</li>" for t in items or []) + "</ol>"

    events = s.get("events", [])
    events_html = ("" if not events else
                   '<div class="tbl"><table><caption>今夜から明朝にかけての主な予定（日本時間）</caption>'
                   '<thead><tr><th>日時</th><th>予定</th><th>重要度</th></tr></thead><tbody>'
                   + "".join(f'<tr><td style="white-space:nowrap">{esc(e.get("time_jst"))}</td><td>{esc(e.get("event"))}</td>'
                             f'<td>{esc(e.get("importance"))}</td></tr>' for e in events)
                   + "</tbody></table></div>")
    watch = s.get("watch_points", [])
    x_note = analysis.get("x_sentiment")

    sections = [f"""<section id="summary">
<h2>サマリー</h2>
<h3>① 米国株市場への影響を意識した直近の動き</h3>{ol(s.get("recent_moves"))}
<h3>② 次の米国市場で見込まれる動き・注意点</h3>{ol(s.get("outlook"))}
{("<h3>注意して見るポイント</h3><ul>" + "".join(f"<li>{esc(w)}</li>" for w in watch) + "</ul>") if watch else ""}
{events_html}
{f'<h3>市場参加者の反応（X・SNS）</h3>{paras(x_note)}' if x_note else ""}
</section>""",
                f'<section id="overview"><h2>主要指標の一覧</h2>'
                f'<p class="msg">{esc(s.get("overview_message") or "各項目の終値と変化。リンクから個別の分析に移動できる。")}</p>'
                f'{overview_table(rows, analysis)}</section>']
    fig_no = 2
    for i, r in enumerate(rows, start=1):
        sections.append(instrument_section(i, r, analysis.get("instruments", {}).get(r["id"], {}), d / "charts", fig_no))
        fig_no += 1 if r.get("tv_symbol") else 0
    sections.append(factcheck_section(len(rows) + 1, rows, fc))

    title = f"マーケット日報 {date}"
    covered = analysis.get("us_session_covered", "")
    html_doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>{CSS}</style></head><body><div class="page">
<header class="doc-header">
<p class="eyebrow">Daily Market Monitor ／ {esc(jp_date(date))} 朝</p>
<h1>{esc(s.get("headline") or title)}</h1>
<p class="lead">日本株・米国株・為替・商品・金利・暗号資産の直近の動きを、米国株市場への影響という観点でまとめた。数字は取得データと照合済み。</p>
<div class="doc-meta"><span>対象の米国取引日: {esc(covered)}</span><span>データ取得: {esc(market.get("fetched_at"))}</span><span><a href="index.html">過去のレポート</a></span></div>
</header>
{"".join(sections)}
<footer class="doc-footer"><span>{esc(title)}</span>
<span>出所: TradingView、日経平均プロフィル、Yahoo Finance、各種報道。投資判断はご自身で。本資料は投資助言ではない。</span></footer>
</div></body></html>"""
    out = ROOT / "reports" / f"{date}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    write_index()
    return out


def write_index() -> None:
    reports = sorted((p.stem for p in (ROOT / "reports").glob("????-??-??.html")), reverse=True)
    items = "".join(f'<tr><td><a href="{r}.html">{esc(jp_date(r))}</a></td></tr>' for r in reports)
    latest = f'<p class="msg"><a href="{reports[0]}.html">最新のレポート（{esc(jp_date(reports[0]))}）を開く</a></p>' if reports else ""
    (ROOT / "reports" / "index.html").write_text(f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>マーケット日報</title><style>{CSS}</style></head>
<body><div class="page"><header class="doc-header"><p class="eyebrow">Daily Market Monitor</p><h1>マーケット日報</h1>
<p class="lead">火曜から土曜の朝に更新。</p></header>
<section><h2>レポート一覧</h2>{latest}<div class="tbl"><table><tbody>{items}</tbody></table></div></section>
</div></body></html>""", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    out = render(args.date)
    print(f"saved {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
