# 毎朝のマーケット日報：ルーチンの作業手順

Claude Code のルーチン（クラウド）が毎朝これを読んで実行する。
数値の取得とチャートの撮影は、ユーザーのPC（毎朝 6:20）が先に済ませて push してある。
PC が動かなかった日は、GitHub Actions（`collect` ワークフロー）が代わりに通常チャートを撮ることがある。
ここでの仕事は **調べて・考えて・書いて・数字をチェックして・HTML にして push する** こと。

## 0. 日付を決めてデータを待つ

```bash
D=$(TZ=Asia/Tokyo date +%F); echo $D
```

- `reports/$D.html` が既にあれば、作成済みなので何もしないで終了する。
- 揃う条件は、`data/$D/market.json` があり、さらに `data/$D/charts_custom/_status.json`（本人の TradingView レイアウトで撮ったチャート）か `data/$D/charts/_status.json`（通常チャート）のどちらかがあること。
- 揃うまで `git pull --ff-only` → 60秒待つ、を繰り返す（最大30回）。1回のコマンドは9分以内に収め、必要なら何回かに分けて実行する。
- 30分待っても揃わなければ、何も書かずに中止する。そのとき `alerts/$D.txt` に「日報を中止した理由（届いていたファイルの一覧も）」を書いて commit・push する（Discord に障害通知が届く）。

## 1. 事実を把握する（ここの数字が「正」）

- `data/$D/market.json` を読む。`instruments[]` の各項目が持つ値は次のとおり。
  - 終値 `close`、前日比 `change_abs`、騰落率 `change`（%）
  - 期間リターン `Perf.W` / `Perf.1M` / `Perf.YTD`
  - 移動平均 `SMA50` / `SMA200`、`RSI`、52週の高値と安値
  - 金利（`jgb10y`, `ust10y`）は `close` が利回り（%）で、`change_abs × 100` が bp の変化幅。`change` は利回りそのものの増減率なので使わない。
  - 日経VIは日経の公式値で、`as_of` がその日付。
- `sectors[]` は米国のセクターETF（SPDR 11業種と半導体 SMH、比較用の SPY）。`change` は前日比（%）、`vs_spy` は SPY との騰落率の差（%ポイント）、`Perf.W` / `Perf.1M` / `Perf.YTD` は期間リターン。
- `warnings` が空でなければ、その項目の数字は本文で断定しない。
- チャートを Read で全部見て（`data/$D/charts_custom/<id>.png` があればそちらを優先し、無ければ `data/$D/charts/<id>.png`。本人のレイアウトには移動平均や一目均衡表などのインジケーターが入っている）、1年の中での位置（高値圏・レンジ・トレンド転換など）をつかむ。日経VIはチャートが無いので、水準の評価は検索で補う。

## 2. 調べる（Web検索。全体で30回程度まで）

対象は、日本時間の今朝までに終わった米国の取引日（土曜朝なら金曜）と、その前の日本の取引日。

- 米国の材料は**英語で**検索する（例: `stock market today Nasdaq close <Month Day, Year>`、`Reuters US stocks close`、`CNBC stocks Dow S&P Nasdaq`）。日本語の記事は前年の同じ日付が混ざりやすいので、記事の年を必ず確かめる。
- 記事本文を WebFetch で開けるのは、許可リストにあるサイトだけ。本文を読みたいときは次のサイトの記事を優先して探す（検索に `site:` を付けてもよい）。
  - 公的機関: federalreserve.gov, bls.gov, bea.gov, home.treasury.gov, eia.gov, boj.or.jp, mof.go.jp, jpx.co.jp
  - 報道・市況: reuters.com, cnbc.com, apnews.com, marketwatch.com, finance.yahoo.com, axios.com, kitco.com, fxstreet.com, coindesk.com, moneyworld.jp, kabutan.jp, traders.co.jp, fx.minkabu.jp, gaitame.com, jiji.com, news.livedoor.com, coindeskjapan.com
- 記事ページを WebFetch で開けないときは、検索結果に出る要約で判断してよい。開けなかったサイト名は最後の報告に書く（許可リストにあるのに開けなかったサイトは、そう分かるように書く）。
- 1つの検索で見つからなくても諦めず、言い方を変えて2〜3回は試す。特に「米国株の材料」と「次の米国取引日の予定」は必ず埋める。

1. 米国株の終値と、その日の主な材料（経済指標・FRB関係者の発言・決算・需給）。主要な報道を2つ以上見る。
2. 15項目それぞれについて、直近で動いた理由（日本株・為替・金利・商品・暗号資産）。
3. **米国のセクター別の動向**（5回程度）。`sectors[]` で上位・下位になったセクターについて、なぜ動いたかを調べる。
   - 例: `sector performance today <Month Day, Year>`、`<セクター名> stocks today why`、`semiconductor stocks <Month Day>`。
   - 見るのは、主な決算・ガイダンス、金利や原油の影響、規制・政策、大型株の個別材料。
   - 景気敏感株（資本財・素材・金融・一般消費財）とディフェンシブ株（生活必需品・公益・ヘルスケア）のどちらに資金が向かったか、グロースとバリューのどちらか、を判断する。1週間・1ヶ月の流れと比べて、一時的な動きか、流れが変わりつつあるかも見る。
4. X（旧Twitter）や SNS で目立った反応。`site:x.com` のような検索でかまわない。取れなければ書かない。
5. 次の米国の取引日に予定されているもの：経済指標、FRB関係者の発言、主な決算、国債入札、期限が近い政治・規制の話題。
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
  "sectors": {
    "headline": "セクター別の動きで言いたいこと1文（例: 半導体主導でハイテクが反発、ディフェンシブは売られた）",
    "analysis": "上位・下位のセクターと、それぞれが動いた理由（3〜5文）",
    "rotation": "資金の流れ（景気敏感とディフェンシブ、グロースとバリュー）。1週間・1ヶ月の流れと比べた評価（2〜3文）",
    "outlook": "次の米国市場で注目するセクターと、その理由（決算・指標・金利など。2〜3文）",
    "sources": [{"title": "記事名", "url": "https://..."}]
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
- `recent_moves` や `outlook` の各項目の頭に「①」などの番号は付けない（表示側で付ける）。
- `events` は空にしない。日時が確定できない予定は `time_jst` を「今週」「11/7（金）」のように書いてよい。

## 4. 数字をチェックする

```bash
python3 scripts/factcheck.py --date $D
```

- `NG` が出たら本文を直して再実行する。直し方は、データに合わせる・external_facts に出典付きで加える・その数字を消す、のいずれか。
- 最大3回まで。3回直しても残る場合はそのまま進む（レポートのチェック欄に表示される）。

## 5. 試運転の自己評価を書く（2026-11-07 まで）

`$D` が 2026-11-07 以前なら、`data/$D/run_eval.json` に今日の作業の評価を書く（Discord の日報に載る）。
ネットワークの許可リストを追加すべきか判断するための記録なので、正直に書く。

```json
{
  "searches": 0,
  "fetch_ok": 0,
  "fetch_failed_domains": ["開けなかったサイトのドメイン"],
  "weak_sections": ["裏付けが取れず薄くなった箇所（例: 米国株の材料、events、X の反応、個別項目名）"],
  "factcheck_first_ng": 0,
  "factcheck_final_ng": 0,
  "allowlist_needed": "要 | 不要 | どちらとも言えない",
  "allowlist_candidates": ["許可すれば内容が良くなりそうなドメイン"],
  "comment": "今日の出来の評価と、その理由（2〜3文）"
}
```

## 6. HTML を作って push する

```bash
python3 scripts/render_report.py --date $D
git add data/$D/ reports/
git commit -m "report: $D"
git push origin HEAD:main || git push origin HEAD:claude/report-$D
```

push すると `publish` ワークフローが GitHub Pages を更新し、Discord に送る。
最後に、headline・factcheck の結果・push 先を短く報告して終わる。
