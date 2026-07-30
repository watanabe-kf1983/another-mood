# Template Specification

## External Design

### 背景: なぜ Undefined をエラーにしないか

Jinja2 は `undefined` クラスを差し替え可能で、厳密な `StrictUndefined`（全ての undefined アクセスでエラー）、チェイン可能な `ChainableUndefined`、デフォルトの `Undefined`（1 階層目はサイレント、チェインはエラー）の 3 段階を提供する。

本プロジェクトは `ChainableUndefined` を採用する。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- デフォルトの `Undefined` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `StrictUndefined` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

## Proposals

### 欠損値の描画責務を finalize 一点に集める (P6 の一部)

エンジンを minijinja へ差し替える（[60-template-trust-model.md](60-template-trust-model.md) の P6）と、**未定義値は Python のフィルタに渡る時点で `None` に潰れる**（`{{ x.a.b | f }}` の `f` が受け取るのは `None`。spike 実測）。jinja2 では番兵オブジェクト自身が「空文字で描かれる」規則を持っていた（`str(Undefined())` == `""`）ため、フィルタは欠損を知らずに済んでいた。この仕組みが失われる。

これは表示の些事ではなく、[10-json-data-model.md](../40-communication/10-json-data-model.md#配列内オブジェクトのフィールド統一) の「nullable な項目は値ではなくフィールドごと省略する」規約の土台に当たる。あの規約は「欠損は undefined の経路を通り、どこでも空文字で描かれる」ことを前提に、「`null` は `"None"` と描かれてしまうから作らない」と決めている。undefined と `null` が Python 境界で合流すると、前提が崩れる。

**実測（jinja2 の `undefined` クラスの `__str__` だけを `"None"` に差し替えてビルド）**: dev-docs 3 ファイル・showcase/music 5 ファイル・showcase/japanese-table-design 2 ファイルの出力に `None` が並ぶ。いずれも `| in_cell` 経路の表セル。

**決定: 描画責務をフィルタから外し、`finalize` の一点に集める。**

- 各フィルタは欠損を自分で文字列化しない。`None` を受けたら `None` を返して「自分の担当外」と表明する（`escape(何も無い)` は何も無い、`url(何も無い)` は何も無い、という素直な意味論でもある）
- 「欠損は何も描かない」を決めるのは `make_environment` の `_finalize` だけ

この配置は既存の `_finalize` の `if value is None` に初めて正当性を与える。同行は現状の外部仕様のどこからも要求されておらず（`docs/` に約束は無く、スキーマは `null` 型を禁じている）、実測でも外しても出力差 0 バイト・落ちるテスト 1 件だった。規則の唯一の持ち主になることで、後付けの安全網から契約へ格上げされる。

**外した案: フィルタ入口で `None` を「空文字で描かれる番兵」へ変換する。** jinja2 の配置をそのまま再現でき、フィルタは無改造で済む。外した理由は、(a) 意図的に渡された `null` と欠損を区別できない、(b) 全フィルタ呼び出しに引数走査の層が乗る、(c) フィルタが `None` を返す形は迂回ではなく素直な意味論であり、番兵という間接層を挟む必要がない。

**フィルタ単位で決めるべき残件**: `link(a, text)` の `text` が未解決だったとき、空のリンクテキスト（jinja2 での現挙動）と label へのフォールバック（`text` 省略時の挙動）のどちらが正しいか。同種の判断が `code_inline` の空コードスパン等にもあるため、フィルタを 1 つずつ見て決める。

### `undefined_behavior` への読み替え (P6 の一部)

上の External Design「なぜ Undefined をエラーにしないか」は minijinja の語彙へ書き換える。3 段階はそのまま対応する: `StrictUndefined` → `strict`、`ChainableUndefined` → `chainable`、デフォルトの `Undefined` → `lenient`。採用は `chainable` で、判断の理由は変わらない。

**minijinja の既定は `lenient`** で、その場合 `{{ x.a }}` が**エラーになる**（jinja2 の既定 `Undefined` と同じ中途半端な段）。明示指定が必須。

16 パターンの実測で `ChainableUndefined` との差は `{{ x | length }}` の 1 つだけ（jinja2 は `0`、minijinja は raise）。実テンプレートの `| length` は 2 箇所とも保護済み（`(row | pluck(x) or []) | length` と定義済み文字列）なので踏まない。
