# 毎朝のマーケット日報：ルーチンの作業手順

Claude Code のルーチン（クラウド）が毎朝これを読んで実行する。
数値の取得とチャートの撮影は GitHub Actions（`collect` ワークフロー）が先に済ませてある。
ここでの仕事は **調べて・考えて・書いて・数字をチェックして・HTML にして push する** こと。

## 0. 日付を決めてデータを待つ

```bash
D=$(TZ=Asia/Tokyo date +%F); echo $D
```

- `data/$D/market.json` と `data/$D/charts/_status.json` が揃うまで、`git pull --ff-only` → 60秒待つ、を繰り返す（最大40回）。
- 40分待っても揃わなければ、何も書かずに「データ未着のため中止」と報告して終了する（Actions 側が障害通知を送る）。
- `reports/$D.html` が既にあれば、作成済みなので何もしないで終了する。

## 1. 事実を把握する（ここの数字が「正」）

- `data/$D/market.json` を読む。`instruments[]` の各項目が持つ値は次のとおり。
  - 終値 `close`、前日比 `change_abs`、騰落率 `change`（%）
  - 期間リターン `Perf.W` / `Perf.1M` / `Perf.YTD`
  - 移動平均 `SMA50` / `SMA200`、`RSI`、52週の高値と安値
  - 金利（`jgb10y`, `ust10y`）は `close` が利回り（%）で、`change_abs × 100` が bp の変化幅。`change` は利回りそのものの増減率なので使わない。
  - 日経VIは日経の公式値で、`as_of` がその日付。
- `warnings` が空でなければ、その項目の数字は本文で断定しない。
- `data/$D/charts/*.png` を Read で全部見て、1年の中での位置（高値圏・レンジ・トレンド転換など）をつかむ。日経VIはチャートが無いので、水準の評価は検索で補う。

## 2. 調べる（Web検索。全体で25回程度まで）

対象は、日本時間の今朝までに終わった米国の取引日（土曜朝なら金曜）と、その前の日本の取引日。

1. 米国株の終値と、その日の主な材料（経済指標・FRB関係者の発言・決算・需給）。主要な報道を2つ以上見る。
2. 15項目それぞれについて、直近で動いた理由（日本株・為替・金利・商品・暗号資産）。
3. X（旧Twitter）や SNS で目立った反応。`site:x.com` のような検索でかまわない。取れなければ書かない。
4. 次の米国の取引日に予定されているもの：経済指標、FRB関係者の発言、主な決算、国債入札、期限が近い政治・規制の話題。
   - 土曜朝の場合、次の米国取引日は月曜なので、週末のイベントリスクにも触れる。

## 3. analysis.json を書く

`data/$D/analysis.json` に、次の形で書く（UTF-8・日本語）。

```json
{
  "report_date": "YYYY-MM-DD",
  "us_session_covered": "2026-10-30（金）",
  "summary": {
    "headline": "全体を一言で（60字以内）",
    "recent_moves": ["① 米国株への影響を意識した直近の動き（3〜5項目）"],
    "outlook": ["② 次の米国市場で見込まれる動き・注意点（3〜5項目）"],
    "watch_points": ["水準・イベントなど具体的な注意点（任意）"],
    "events": [{"time_jst": "11/3 22:30", "event": "9月JOLTS求人件数", "importance": "高"}],
    "overview_message": "一覧表の見出し文（1文）"
  },
  "instruments": {
    "<market.json の id>": {
      "headline": "この項目で言いたいこと1文",
      "analysis": "動きと背景（2〜4文。チャートで見える1年の中での位置にも触れる）",
      "us_impact_level": "大 | 中 | 小 | なし",
      "us_impact": "米国株市場への影響（2〜3文）。影響が小さければ「米国株への影響は限定的」とはっきり書き、その理由も書く",
      "sources": [{"title": "記事名", "url": "https://..."}]
    }
  },
  "external_facts": [
    {"label": "9月CPI前年比", "value": "3.1%", "sources": ["https://...", "https://..."]}
  ],
  "x_sentiment": "XやSNSで目立った反応（2〜3文。無ければ省略）"
}
```

`instruments` には、market.json の15項目すべての id を入れる（`nikkei225, jpx400, growth250, nk_futures, nikkei_vi, usdjpy, dow, nasdaq, sp500, btc, wti, gold, platinum, jgb10y, ust10y`）。

### 数字の書き方（チェックスクリプトが機械的に照合する）

- 市場の数字は `market.json` の値だけを使う。四捨五入はしてよい（例：-2.1178 → -2.12% や -2.1%）。
- 書き方は半角の数字と単位にする（例：`63,290円`、`-2.12%`、`+8.4bp`、`157.57円`）。「6万3290円」のような漢数字混じりは使わない。
- 上昇・下落は符号付きで書くか、「〜下落」のように文で示す。符号付きで書くなら、データと同じ向きにする。
- 自分で計算した数字（2つの値の差など）は書かない。
- 指標・決算・発言など、market.json に無い数字を書くときは、必ず `external_facts` に値と出典URL（2つ以上）を入れる。

### 内容の方針

- 「米国株市場への影響」が主な観点。日本の項目でも、米国株にどう効くのか（効かないのか）を書く。
- 推測は推測と書く（「〜の可能性」「〜が意識されやすい」）。売買の推奨はしない。
- サマリーの①は**起きたこと**、②は**これから注意すること**。日付・時刻は日本時間で書く。

## 4. 数字をチェックする

```bash
python3 scripts/factcheck.py --date $D
```

- `NG` が出たら本文を直して再実行する。直し方は、データに合わせる・external_facts に出典付きで加える・その数字を消す、のいずれか。
- 最大3回まで。3回直しても残る場合はそのまま進む（レポートのチェック欄に表示される）。

## 5. HTML を作って push する

```bash
python3 scripts/render_report.py --date $D
git add data/$D/analysis.json data/$D/factcheck.json reports/
git commit -m "report: $D"
git push origin HEAD:main || git push origin HEAD:claude/report-$D
```

push すると `publish` ワークフローが GitHub Pages を更新し、Discord に送る。
最後に、headline・factcheck の結果・push 先を短く報告して終わる。
