# Template Specification

## External Design

### 背景: なぜ undefined アクセスをエラーにしないか

minijinja は `undefined_behavior` で undefined アクセスの扱いを選べる: 厳密な `strict`（全ての undefined アクセスでエラー）、チェイン可能な `chainable`、既定の `lenient`（1 階層目はサイレント、`{{ x.a }}` のチェインはエラー）の 3 段階を提供する。

本プロジェクトは `chainable` を明示指定する（既定のままでは `{{ x.a }}` がエラーになる）。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- `lenient` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `strict` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

なお `chainable` でも minijinja 組込みフィルタは undefined を受けない（`{{ x | length }}` は raise。jinja2 の `ChainableUndefined` は `0` を返した）。次節の「何も描かない」規則が及ぶのは本ツールのヘルパー。

### 欠損値は何も描かない

欠損した値をテンプレートが描こうとしたとき、出力は空になる。フィルタや関数を通した場合も同じで、ヘルパーが `"None"` のような表現を発明することはない。この規則があるので [10-json-data-model.md](../40-communication/10-json-data-model.md#配列内オブジェクトのフィールド統一) の「nullable な項目は値ではなくフィールドごと省略する」規約が成り立つ。

**欠損と「壊れた参照」は別に扱う。** 解決を試みて外した参照（missing node）は目立つ `[text]` を出す。一方 optional フィールドの欠損は上の規約が認めている正常系なので、目立たせず何も描かない。`node` / `child` の住所を組み立てる引数が欠損したときは、参照そのものが成立しないので missing node にもならず、何も描かれない。

**`link` の表示テキスト。** 引数を渡さなければ label、渡した値が欠損していれば空のテキスト（`[](url)`）になる。参照は健在なので、表示テキストの欠損でリンクごと消すことはしない。

### テンプレートの語彙は filter / test / operator に限る

値そのものはメソッドを持たない。minijinja の `pycompat` は Python の文字列 / list / dict メソッドを値に生やすが、これを切っている（`.startswith()` は空描画ではなくメソッド名つきのエラー）。

理由は **利用者に案内できる境界が引けること**。pycompat を入れたままだと「どこまでが Python 相当か」を答える主体が居ない — 本ツールの `docs/` には書けず（Python のどの版のどのメソッドか特定できない）、minijinja コアの保証でもない（実体は minijinja-contrib の `unknown_method_callback` で、上流の位置づけも「Jinja2 テンプレートの移行互換シム」。COMPATIBILITY.md も *Filters should generally be used instead of methods* と述べる）。語彙を filter / test / operator に閉じれば、案内できる集合とテンプレートから届く集合が一致する。

## Internal Design

### 欠損の描画責務と「引数未指定」の区別

`None` は「値が欠損している」の意味に予約する。「引数が渡されていない」には番兵 `OMITTED`（`omitted.py`）を使う。既定値を `None` にすると 2 つが区別できず、最も重い失敗は `node(path=…)` で起きる — `path` の欠損で prefix が空になり、`node("y", path=欠損)` が `/y` に解決して**別の実在ノードへ静かにリンクする**。表示の劣化ではなく誤リンク。

欠損を描くのは `_finalize` 一点で、ヘルパーは欠損を文字列化せず `None` を返す。テキストを被写体に取るものは境界（`as_template_helper`）が包むので、欠損はプロセッサに届かない。

引数の欠損は結果ごと消さず、その引数が担う仕事だけを失わせる。引数が何をするかで 3 通りに分かれる:

- **表示に混ざるだけ**（`link` の `text`）→ その箇所が空になる
- **出力の形を選ぶ**（`code_fenced` の `language`、`to_yaml` の `flow`）→「渡されていない」と同じ扱い
- **住所を組み立てる**（`node` の `segs` / `path` / `fragment`、`child` の `seg`）→ 参照が成立しないので `None`。ここだけ「空にする」が使えない（上の誤リンクになる）

番兵を入れるのは、この 3 通りのうち「渡されていない」と挙動が分かれるものだけ。例外は 2 つあり、`under_heading` の `marker` は既定値が無く、囲みの深さが決まらないと描けないので raise のまま（欠損を静かに扱わない唯一の場所）。コレクションを返す `walk_entity` は空コレクションを返す（`{% if rows %}` / `for` が回る形を保つ）。

#### 背景: 外した 2 案

**フィルタ入口で `None` を「空文字で描かれる番兵」へ変換する。** jinja2 の配置をそのまま再現でき、フィルタは無改造で済む。外した理由は、(a) 意図的に渡された `null` と欠損を区別できない、(b) 全フィルタ呼び出しに引数走査の層が乗る、(c) フィルタが `None` を返す形は迂回ではなく素直な意味論であり、番兵という間接層を挟む必要がない。

**`link` の `text` が欠損したら label へフォールバックする。** リンクが使える形で残るのは利点だが、著者が `t.別名` と書いたのに黙って `名前` を出すのは、フィルタに暗黙の `default()` を埋め込むこと。フォールバックが要る著者には `t.別名 or t.名前` / `| default(...)` という明示手段があり、*explicit is better than implicit* に反する。データ欠損が出力から検出できなくなる点も悪い（空なら表セルが空くので気づける）。

## Proposals

### build_info (P14)

CI でビルドしたサイトに git commit id やビルド時刻を刻めるようにする。ビルドをとりまく事実（誰が・何を・どんなパラメータで処理したか）をテンプレートから文字列キーで照会する関数 `build_info` を追加する。

```jinja
{{ build_info("vars.git_commit_id") }}
{% for k, v in build_info() | dictsort %}{{ k }}: {{ v }}{% endfor %}
```

- **単複同名**: 引数ありで一件（文字列）、引数なしで全量（dict）。Java `System.getenv` / R `Sys.getenv` の形
- **不在は undefined**: 未設定キーは undefined を返し、「欠損値は何も描かない」規則に従い空描画。`| default("(dev)")` で受けられる。ローカルビルドで vars が未設定でもテンプレートは壊れない
- **ストアはフラットな文字列キー → 文字列値**。ドットは階層構文ではなくただの文字（照会時のパース処理は無い）。値は供給元の型によらず全て文字列に統一

#### キーの名前空間 — 出所で三分する

| 名前空間 | 出所 | 例 |
|---|---|---|
| `manifest.*` | プロジェクトの宣言 (sbdb.yaml) | `manifest.title`, `manifest.sbdb_version` |
| `processor.*` | 今回処理した処理系 | `processor.name`, `processor.version`, `processor.config.out_dir` |
| `vars.*` | 実行者の注入値 (env / CLI / MCP — 供給機構は [20-config-spec.md](../20-app/20-config-spec.md) の Proposals) | `vars.git_commit_id` |

- `processor` は sbdb スペック自身の語彙（manifest の `tools.<processor>`）。ツールのブランドはキーや関数名には現れず、`processor.name` の**値**として現れる（改名してもテンプレートの綴りは無傷）
- `processor.name` の値は manifest の `tools.` 直下キーと同綴りの **id**。これにより `"manifest.tools." ~ build_info("processor.name") ~ ".minimum_version"` という動的照会が合流する
- 注入ルート（vars）は `vars.*` にしか書けない。`processor.*` / `manifest.*` を外から偽装する経路は無い

#### docs 契約 — vars.* と関数 API のみ約束する

利用者向け docs で約束するのは、関数の仕様と `vars.*` の注入規約（利用者が書く側なので契約が要る）だけ。`manifest.*` / `processor.*` のキー目録は**意図的に非契約**とし、「処理系が供給するもので、目録はバージョン間で変わりうる。列挙で確認せよ」と docs に明言する（沈黙を暗黙の安定保証に読ませない）。release.md の feature / breaking 判定は「docs/reference の約束の集合」に基づくため、目録を約束しないことでキーの増減・改廃がリリース分類上の破壊にならない。

#### 背景: 外した案

- **データ層に流す（normalized content 化）** — views / tap / `__data` 診断に載る一体感は魅力だが、views に現れるデータが contents から一意に定まらず実行環境で変わるのは受け入れない。views / tap のデータは Git にコミットされたソースから決まるべきで、ビルド時情報は**ドキュメント（レンダリング結果）にのみ現れる**。この裁定の帰結として、診断は `__data` ではなくメタテンプレートのページ（または `__build_report` への記録）で行う
- **環境変数の素通し (`env.*`)** — テンプレートが環境の読み取り器になり、CI の環境（AWS クレデンシャル等）を出力に焼き込める。[60-template-trust-model.md](60-template-trust-model.md) の閉じた値モデルに穴を開けるため不可。越境するのは実行者が `MOOD__VARS__*` / `--var` で明示的に差し出した値だけ
- **属性アクセス（`build.vars.commit` 等のコンテキスト注入）** — スキーマが保証するフィールドの顔になる。この情報はツール・実行環境依存で取得無保証の Optional であり、「文字列キーによる照会」という構文自体にその性格を語らせる。データ名前空間への予約名追加も不要になる（予約されるのは関数名一個 — `node` と同じ扱い）
- **汎用フィルタでの照会（`child` 等）** — 汎用語彙は record を通貨とするため `.value` の一段が常に付き、`child` の未解決は MissingNode として目立つ（「未設定が正常」な Optional には逆向き）。既存の `child` は id 照会フィルタとして今回の検討と独立に有用（実装・文書化済み）
- **関数名の別候補** — `mood.*`（ツール名を語彙に入れない — P4 `mood_view` → `render` と同じ裁定）、`build_context`（docs 既定義の「Template context」と概念衝突）、`env`（素通し期待を招き、慣習上の二義 — OS env 素通し / 実行モード — のどちらでもない）、`provenance`（裸名詞に錨が無い）。`build_info` は三名前空間すべてを「このビルドという出来事についての事実」として束ねる唯一の錨

#### 実装スコープ

1. 供給機構（config 層 — 20-config-spec.md 側）と `build_info` 関数 + `vars.*`
2. `processor.*` / `manifest.*` の初期セット（`name` / `version` / `config.*`、manifest の dotted 平坦化）
3. docs: 関数リファレンス + vars 注入規約 + 非契約の明言 + 列挙慣用句（colophon の実例）
4. 診断用メタページは後続で可（列挙一行で自作できるため必須ではない）
