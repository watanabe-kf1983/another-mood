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

CI でビルドしたサイトに git commit id やビルド時刻を刻めるようにする。ビルドをとりまく事実（誰が・何を・どんなパラメータで処理したか）を、テンプレートから文字列キーで照会する `build_info(key, default)` を置く。関数とストアと `processor.*` は #1 で実装済みで、以下は残る 5 PR の分。

```jinja
{{ build_info("vars.git_commit_id", "(dev)") }}
```

- **`| default()` はこの関数には効かない**（実測）。minijinja の `default` は undefined にしか反応せず、Python 側で登録したグローバルが返せる不在は none 止まりのため。効くのは第二引数と `or "(dev)"`。#2 の docs / showcase の例は第二引数で書く

#### キーの名前空間 — 出所で三分する

| 名前空間 | 出所 | 例 |
|---|---|---|
| `processor.*` | 今回処理した処理系 | `processor.name`, `processor.version`, `processor.started_at` |
| `vars.*` | 実行者の注入値 (env / CLI / MCP — 供給機構は [20-config-spec.md](../20-app/20-config-spec.md) の Proposals) | `vars.git_commit_id` |
| `manifest.*` | プロジェクトの宣言 (sbdb.yaml) | `manifest.title`, `manifest.sbdb_version` |

- `processor.name` の値は manifest の `tools.` 直下キーと同綴りの **id**。これにより `"manifest.tools." ~ build_info("processor.name") ~ ".minimum_version"` という動的照会が合流する（#6 の前提）
- 注入ルート（vars）は `vars.*` にしか書けない。`processor.*` / `manifest.*` を外から偽装する経路は無い（#4 / #5 の制約）

#### 列挙は関数ではない — 奥付テンプレートの subject

ストアの全量は、関数ではなく**奥付テンプレートの subject** として渡す。reconcile が奥付を独立したテンプレートとして `render`（文字列を返す）し、その結果をページ末尾に追記する。

```jinja
{% for k, v in _ | dictsort %}{{ k }}: {{ v }}{% endfor %}
```

「列挙するのは奥付、キー照会するのは利用者テンプレート」という役割分担を、供給する語彙の違いとして構造に出す。全量を返す関数（`build_info_all` 等）は持たない。

#### 奥付 — 表紙とビルド失敗ページの末尾

ストアの全量列挙を、reconcile が 2 か所の末尾に追記する:

- **表紙** (`index.md`) — 成功ビルドで公開される唯一の奥付
- **ビルド失敗ページ** — 失敗ページは表紙を置き換えるので、失敗時に読者が見る唯一のページになる

警告ページ (`warnings.md`) は対象外。奥付を持つ表紙の隣にぶら下がるだけなので、重ねる意味がない。

**追記は reconcile が一手に引き受ける。** 生成側（cover テンプレート）は build_info を知らない。理由は末尾の順序が一箇所で決まること — 現状 `_append_warnings_link` が表紙の末尾に警告リンクを足すので、生成側で奥付を描くと奥付の下に警告リンクが来る。順序は **本文 → 警告リンク → 奥付** とし、警告リンクの差し込み位置を奥付の手前に変える。

**奥付は自動で、利用者が外す手段を持たない。** そのぶん何を載せるかの敷居は高い、という性格になる（次節の `processor.config.*` の裁定はこれに基づく）。

#### processor.* の初期セット

| キー | 値 |
|---|---|
| `processor.name` | manifest の `tools.` 直下キーと同綴りの id |
| `processor.version` | 動いている処理系の版 |
| `processor.started_at` | 処理系の起動時刻 |
| `processor.config.project_dir` | 入力プロジェクトの絶対パス |

`started_at` の**表示用の別書式キーは作らない**（体裁の方針をツールが発明することになる）。値は watch ではセッション開始時刻で、再ビルドしても動かない。

##### キーを足す場所 — `Workspace` の `build_info` property

#3 / #6 で足すキーは `Workspace` が既に型付きで持っている値（`config` / `manifest`）の平坦化なので、上流で組んで運ぶ形にはしない（同じ事実が二重に載る）。追加は property に一行足す形になる。

ただし `pipeline/` はカバレッジ計測対象外なので、**アルゴリズムと呼べるもの**（#6 の manifest 平坦化など）は `components/shared/` に汎用ヘルパとして置き、`Workspace` はそれを呼ぶ。property が持つのは「どのキーがどの源から来るか」だけに保つ。

**`processor.config.*` は `project_dir` だけ。** `out_dir` / `site_dir` / `tmp_dir` は入れない。入力と出力で答えている問いが違うため:

- **入力** — 「いま見ているこれは、どのソースから出たのか」。開いた後にしか湧かない問いで、ビルド時の CLI 出力では答えられない。複数プロジェクトが同居するリポジトリ、`mood watch` のプレビュー、移動・改名した後に残った古い出力で実際に必要になる
- **出力** — 「これはどこに書かれたのか」。読者はそれを開いている最中なので既に知っている

`namespace_root` / `host` / `port` も入れない。前者は境界層が縛る内部値、後者は watch 専用で出力に意味を持たない。

`project_dir` は絶対パスで入れる。`namespace_root` からの相対 tail にすれば漏洩は減るが、MCP では `namespace_root == project_dir` なので tail が `.` に潰れて何も言わなくなる。チャネルによって情報量が変わる識別子は識別子として使えない。

##### 背景: 「公開物にローカルパスを出さない」を奥付には当てない

現状、絶対パスが出力に現れるのはビルド失敗ページだけで（`Diagnostic.to_entry` が `resolve()` して焼く）、成功して公開されるものには現れない。この線を跨ぐことになるが、跨ぐと判断した。表紙の奥付も失敗ページも、読者はビルドした人であり、公開ページ上でもそこは変わらない。線はフィールドの線ではなく読者の線だった。

#### docs 契約 — vars.* と関数 API のみ約束する

利用者向け docs で約束するのは、関数の仕様と `vars.*` の注入規約（利用者が書く側なので契約が要る）だけ。`processor.*` / `manifest.*` のキー目録は**意図的に非契約**とし、「処理系が供給するもので、目録はバージョン間で変わりうる。**表紙の奥付で確認せよ**」と docs に明言する（沈黙を暗黙の安定保証に読ませない）。release.md の feature / breaking 判定は「docs/reference の約束の集合」に基づくため、目録を約束しないことでキーの増減・改廃がリリース分類上の破壊にならない。

自動列挙の帰結として、**`vars.*` に注入した値は全て表紙に出る**。一つのテンプレートで使うつもりで注入した値も載るので、docs に明記する。

奥付のタイムスタンプにより、**毎回のビルドが必ず差分を生む**。ビルド結果をコミットする利用者は表紙の `index.md` が毎回汚れる（奥付が載る成功時のファイルはこれ一つなので、除外するならこの一ファイルで足りる）。動かないタイムスタンプに意味はないので、これは代償ではなく仕様。

#### 背景: 外した案

- **データ層に流す（`__build_info` としてシステム定義エンティティ化）** — 機構としては成立する。`__definition` に先例があり（`schema_inspector` が preprocess で `__builtin/__definition.json` を吐き、views が `from: __definition.entities` で読み、`__data` にも tap にも乗る）、同じ経路に `__build_info` を足せる。tap から覗ける・`__data` 診断に自動で乗る・views から join できる、という利点も実在する。外した理由は 2 つ。(a) **views の出力が実行環境で変わるようになり、これは一方通行**。views が読めるようにした後で取り上げると利用者の views が壊れる。逆向き（奥付方式から後で data 層へ移す）は余地が残る。(b) **ビルド失敗ページに届かない**。preprocess で吐く以上、上流で失敗すれば reconcile からは見えず、上の 2 か所という要件の片方が原理的に成立しない。なお views から build info を読みたい用途は現時点で無い
- **tap に provenance を載せる** — 上の代替として検討したが作らない。tap 出力は差分を取る使い方が主なので、毎回動く値が混ざると実質的な差分がノイズに埋もれる。守る線は「ソースだけで決まる」ではなく **「マシンと起動のしかたには依存しない」**（tap 出力には既に `__definition` 等のツール生成目録が乗っており、ツール版には依存している）。将来必要になったら、置き場はドキュメントの中ではなく外（`BuildResult` か隣接ファイル）
- **関数ではなくマッピングをグローバル登録する（`build_info["vars.git_sha"]`）** — 添字アクセスの不在は undefined になるので `| default()` がそのまま効く（実測）。外した理由は 2 つ。Python の dict のメソッドがテンプレートに漏れる（`build_info.items` が `<built-in method items>` を描く。`pycompat=False` で閉じたはずの穴）。任意の利用者テンプレートから全量を列挙でき、上の「列挙は奥付の subject」が崩れる
- **環境変数の素通し (`env.*`)** — テンプレートが環境の読み取り器になり、CI の環境（AWS クレデンシャル等）を出力に焼き込める。[60-template-trust-model.md](60-template-trust-model.md) の閉じた値モデルに穴を開けるため不可。越境するのは実行者が env / `--var` / MCP で明示的に差し出した値だけ
- **属性アクセス（`build.vars.commit` 等のコンテキスト注入）** — スキーマが保証するフィールドの顔になる。この情報はツール・実行環境依存で取得無保証の Optional であり、「文字列キーによる照会」という構文自体にその性格を語らせる。データ名前空間への予約名追加も不要になる（予約されるのは関数名一個 — `node` と同じ扱い）
- **汎用フィルタでの照会（`child` 等）** — 汎用語彙は record を通貨とするため `.value` の一段が常に付き、`child` の未解決は MissingNode として目立つ（「未設定が正常」な Optional には逆向き）。既存の `child` は id 照会フィルタとして今回の検討と独立に有用（実装・文書化済み）
- **関数名の別候補** — `mood.*`（ツール名を語彙に入れない — P4 `mood_view` → `render` と同じ裁定）、`build_context`（docs 既定義の「Template context」と概念衝突）、`env`（素通し期待を招き、慣習上の二義 — OS env 素通し / 実行モード — のどちらでもない）、`provenance`（裸名詞に錨が無い）。`build_info` は三名前空間すべてを「このビルドという出来事についての事実」として束ねる唯一の錨

#### 実装スコープ — PR の並び

1 PR ずつ独立して確認できる形に刻む。並びの原則は、**利用者から見える面を持たない土台を先に置き、供給チャネルを後から足す**こと。#1（関数・ストア・`processor.*`）は実装済み。

| # | 内容 | store に増えるキー |
|---|---|---|
| 2 | 奥付テンプレート + reconcile による追記 + `docs/` 公開 + showcase の実例 | — |
| 3 | config → ストアの経路 | `processor.config.project_dir` |
| 4 | vars — `ProjectConfig.vars` + env チャネル | `vars.*` |
| 5 | CLI `--var` + MCP `build` の `vars` | — |
| 6 | `manifest.*`（dotted 平坦化・`Manifest` に生 mapping 保持） | `manifest.*` |

- #2 で初めて利用者から見える。この時点の奥付は `processor.*` の 3 キーだけ
- #4 の着手前に env の綴りを決める（[20-config-spec.md](../20-app/20-config-spec.md) の Proposals）
- #6 を最後に置いたのは、`manifest.*` が他のどれの前提でもないため。`Manifest` が生 mapping を保持する形に変わるので、レビューの観点も他と違う
