# Template Specification (appendix)

[Template Specification](../../../20-design/70-generator/20-template-spec.md) の背景。

## なぜ undefined アクセスをエラーにしないか

minijinja は `undefined_behavior` で undefined アクセスの扱いを選べる: 厳密な `strict`（全ての undefined アクセスでエラー）、チェイン可能な `chainable`、既定の `lenient`（1 階層目はサイレント、`{{ x.a }}` のチェインはエラー）の 3 段階を提供する。

本プロジェクトは `chainable` を明示指定する（既定のままでは `{{ x.a }}` がエラーになる）。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- `lenient` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `strict` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

なお `chainable` でも minijinja 組込みフィルタは undefined を受けない（`{{ x | length }}` は raise。jinja2 の `ChainableUndefined` は `0` を返した）。[欠損値は何も描かない](../../../20-design/70-generator/20-template-spec.md#欠損値は何も描かない)の規則が及ぶのは本ツールのヘルパー。

## 語彙を filter / test / operator に閉じる理由

minijinja の `pycompat` を入れたままだと、テンプレートの語彙に「Python 相当のメソッド」が加わる。しかし、その範囲を利用者に案内できる主体が居ない:

- 本ツールの `docs/` には書けない。どの版の Python のどのメソッドが使えるかを特定できない
- minijinja コアの保証でもない。実体は minijinja-contrib の `unknown_method_callback` で、上流は「Jinja2 テンプレートの移行互換シム」と位置づけ、COMPATIBILITY.md も *Filters should generally be used instead of methods* と述べる

語彙を filter / test / operator に閉じれば、docs に書ける集合とテンプレートから届く集合が一致し、利用者に案内できる境界が引ける。

## 出力フォーマットの課題

テンプレートエンジンに出力フォーマット別の escape 機構が無いと、ユーザ入力に出力フォーマットの特殊文字 (Markdown なら `*` `_` `|` `` ` `` `<` 等) が混じった瞬間に出力が壊れる。Jinja2 標準の `autoescape` は HTML escape 決め打ちで、Markdown / Mermaid / AsciiDoc / SQL 等の非 HTML フォーマットに直接は使えない。

複数フォーマットを並行サポートしつつ、フォーマット別の escape をテンプレート著者の書き忘れに頼らず保証できる機構が要る。

## Escape 方針を ASCII punctuation 一律にした理由

- **網羅的安全性**: 見出し / リスト / 引用 / Thematic break / 表セル / 強調 / inline code / 生 HTML タグ / 既存 escape / HTML entity の全構文記号を 1 ルールで防げる。「想定外の入力で崩れる」事故が起きない
- **レンダリング上の副作用なし**: CommonMark の backslash escape は表示上は escape 前と同じになるため、不要な escape が混じっても出力品質が落ちない
- **実装の単純性**: 「文脈別に必要最小限の escape を行う」方式は安全だが、文脈判定が複雑になり保守コストが高い

## 欠損の描画で外した 2 案

**フィルタ入口で `None` を「空文字で描かれる番兵」へ変換する。** jinja2 の配置をそのまま再現でき、フィルタは無改造で済む。外した理由は、(a) 意図的に渡された `null` と欠損を区別できない、(b) 全フィルタ呼び出しに引数走査の層が乗る、(c) フィルタが `None` を返す形は迂回ではなく素直な意味論であり、番兵という間接層を挟む必要がない。

**`link` の `text` が欠損したら label へフォールバックする。** リンクが使える形で残るのは利点だが、著者が `t.別名` と書いたのに黙って `名前` を出すのは、フィルタに暗黙の `default()` を埋め込むこと。フォールバックが要る著者には `t.別名 or t.名前` / `| default(...)` という明示手段があり、*explicit is better than implicit* に反する。データ欠損が出力から検出できなくなる点も悪い（空なら表セルが空くので気づける）。
