# DB 自己記述

ユーザが書いたスキーマ定義とビュー定義を、ツールが内蔵のテンプレートで自動的に可視化する機能。出力は `__db/` に置く。

## External Design

- ビュー定義ページは Shape (各出力フィールドの型 + entity ref) を出し、Query Object の `derive` がそれを生成する。複合型を許容する本ツールでは、カラムヘッダとサンプル行だけでは結果形状が伝わらないため（[背景](../../90-appendix/20-design/75-meta-documentation/10-database-information.md#view-の-shape-が必須な理由)）

### DB 自己記述の置き場所

`__db` マウントと各アンカールート（`__entity_defs` 等）はどちらも `__` 始まりだが要求する事情は別レイヤ: `__db` は edition 名のユーザ空間（`__` 始まりは検証で禁止）との衝突回避、`__entity_defs` はグローバル node_map でのユーザ entity/view 名との衝突回避。ゆえに `__db/entity_defs` にはできず `__db/__entity_defs` になる（[予約プレフィックス](../40-communication/10-json-data-model.md#予約プレフィックス)）。診断系は `__db` 内で edition 横断・常に同位置。

出力は **deliverable（著者の reports）と DB 自己記述（`__db/`）の 2 種**で捉え、表紙で reports を前面・`__db/` を控えめな別エントリに置く。`__db/` を reports / edition の軸には混ぜない（自己記述面を「体裁違いのレポート」に誤ラベルさせないため）。`__build_info/`（奥付）と `__warnings/`（警告ページ）は reconcile の build-report 層で自己記述とは別軸ゆえ `{outDir}` 直下、リンクは表紙 `index.md` に append。

## Internal Design

### meta 診断の分割

> **[W4 dup]** ↔ meta_templates.py:133-139 META_EDITION docstring (a, 完全)。案: 削除→コード。「別ページが要るならノードを一つ立てる」決定は残す

meta 診断ページ（`__entity_defs` / `__view_defs` / `__data`）の主題は **実データツリーノード**（`resources/views/` のビルトインビューが生む）で、分割は通常の[分割ルール](../70-generator/20-template-spec.md#分割ルール)そのもの。meta には利用者の `reports.yaml` が無いので paging は固定（`META_EDITION.paging`）。

> **決定: 別ページが要るならノードを一つ立てる.** 1 ノードは（データ位置で定まる）1 ページにだけ描かれる。同一 entity を Definition と Data の 2 ページに出すのに `__entity_defs` / `__data` の **2 ビュー＝2 アンカールート**を立てるのがこの実践 — 予約キーや fallback で 1 ノードを複数ページに割る手は採らない。

## Proposals

### 内部オブジェクト診断の `--debug` 復活スイッチ

`__definition.*` やメタビュー自身のページは `where.not` で抑止しているが、カタログ自体をデバッグしたい場面 (built-in の挙動を疑うとき等) では見たくなりうる。その際は `mood build --debug` 相当のスイッチで `where.not` を外し、内部オブジェクトのページも出す案。常時は出さず opt-in にすることで、通常出力のノイズと debug 時の網羅性を両立する。スイッチの粒度 (build 全体か meta だけか) は実装時に確定。
