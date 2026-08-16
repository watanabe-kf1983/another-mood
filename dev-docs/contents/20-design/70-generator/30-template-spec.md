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

### 奥付

奥付はストアの全量を列挙する独立ページ (`__build_info/`) で、表紙 (`index.md`) からはリンク節 (`## Build Information`) だけが張られる。`__warnings/` `__db/` と同じ形で、表紙の節見出しは `Database Information` に倣った綴り（パスの綴りは関数名 `build_info` 側に揃える）。

**ファイル境界を分けるのは、利用者が公開対象から外せるようにするため。** 奥付が語るのはビルドした環境の事実（実行者が注入した値、入力プロジェクトの絶対パス等）で、出力を公開する利用者にとっては読者が「ビルドした人」ではなくなる。表紙に混ぜ込むと外す手段が無いが、ディレクトリが分かれていれば `__build_info/` 一つを除外指定するだけで済む。ビルド結果をコミットする利用者にとっても、毎回動くタイムスタンプで表紙が汚れなくなる（動かないタイムスタンプに意味はないので、差分が出ること自体は仕様）。

**除外機構はツールに持たせない。** 何を公開するかはデプロイ手段（rsync / `aws s3 sync` / CI）の仕事で、ツールが公開ポリシーのフラグを持ち始めると同種の要求が積み上がる。ツールが負うのは「一箇所にまとまっていること」だけ。`__warnings/` も同じ立場。

**表紙のリンク節に値は載せない。** 要約を載せると「どのキーが表紙に値するか」という裁定が復活し、下の非契約宣言と衝突する。

**config は選ばず全量載せる**（`processor.config.*`）。奥付が答えるのは「この run はどう起動されたか」で、config はその問いそのもの。部分集合にすると「どれが有用か」というツール側の趣味判断になる。`host` / `port` のように build では効かないパラメータも並ぶが、run の種別は `processor.command` として同じページにある。

**行が無いことは「その run でそれが起きなかった」を意味する**（watch に `site_dir` が無いのは publish しないから）。空欄の行を置くと `build_info(key, default)` の `default` が効かなくなる。この読み方を守るため、config が語らない実効値は別のキーで出す（作業ディレクトリ → `processor.workspace.*`）。値の書式はツールが発明しない（時刻は ISO 8601 一本、bool は YAML 綴り）。

パスは絶対で載せる。`namespace_root` 相対の tail は MCP で `.` に潰れ、チャネルによって情報量が変わる識別子になる。ローカルパスが公開物に出ることは、上のファイル境界で受け止める。

**ビルド失敗ページだけは奥付を埋め込む。** 失敗ページを読むのは必ずビルドした人であり、失敗した出力を公開する利用者は居ない。診断が既に絶対パスを焼いているページでもある。

`processor.*` / `manifest.*` のキー目録は `docs/` で**意図的に非契約**とし、「処理系が供給するもので、目録はバージョン間で変わりうる。奥付ページで確認せよ」と明言する（沈黙を暗黙の安定保証に読ませない）。release.md の feature / breaking 判定は「docs/reference の約束の集合」に基づくため、目録を約束しないことでキーの増減・改廃がリリース分類上の破壊にならない。

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

### build_info のキーを足す場所 — `Workspace` の `build_info` property

キーは `Workspace` が既に型付きで持っている値の平坦化なので、上流で組んで運ぶ形にはしない（同じ事実が二重に載る）。ただし `pipeline/` はカバレッジ計測対象外なので、平坦化そのものは `components/shared/` の汎用ヘルパに置く。property が持つのは「どのキーがどの源から来るか」だけ。

`processor.config.*` は config の写しで、実効値は混ぜない。ずれるのは作業ディレクトリだけ — `tmp_dir` 未固定なら config には無いが、使い捨てのディレクトリは実在する。これを `processor.workspace.*`（`root` / `temporary`）として分ける。内部エラーの run はこのディレクトリを post-mortem 用に残すので（`command._discard_workspace`）、奥付を埋め込むビルド失敗ページでは残存パスとして読める。`temporary` が要るのは、`root` が「消えた使い捨て」か「利用者が固定したディレクトリ」かで読み方が変わるため。

## Proposals

### build_info (P14)

CI でビルドしたサイトに git commit id やビルド時刻を刻めるようにする。ビルドをとりまく事実（誰が・何を・どんなパラメータで処理したか）を、テンプレートから文字列キーで照会する `build_info(key, default)` を置く。関数・ストア・`processor.*` の 3 キーは #1、奥付と `docs/` 公開は #2、奥付の独立ページ化と `processor.command` は #3、`processor.config.*` は #4 で実装済みで、以下は残る 3 PR の分。

```jinja
{{ build_info("vars.git_commit_id", "(dev)") }}
```

#### キーの名前空間 — 出所で三分する

| 名前空間 | 出所 | 例 |
|---|---|---|
| `processor.*` | 今回処理した処理系 | `processor.name`, `processor.version`, `processor.started_at`, `processor.command` |
| `vars.*` | 実行者の注入値 (env / CLI / MCP — 供給機構は [20-config-spec.md](../20-app/20-config-spec.md) の Proposals) | `vars.git_commit_id` |
| `manifest.*` | プロジェクトの宣言 (sbdb.yaml) | `manifest.title`, `manifest.sbdb_version` |

- `processor.name` の値は manifest の `tools.` 直下キーと同綴りの **id**。これにより `"manifest.tools." ~ build_info("processor.name") ~ ".minimum_version"` という動的照会が合流する（#7 の前提）
- 注入ルート（vars）は `vars.*` にしか書けない。`processor.*` / `manifest.*` を外から偽装する経路は無い（#5 / #6 の制約）

#### docs 契約 — vars.* の注入規約は #5 で約束する

関数 API とキー目録の非契約宣言は #2 で書いた（External Design の「奥付」節）。残るのは `vars.*` の注入規約で、利用者が書く側なので契約が要る。

自動列挙の帰結として、**`vars.*` に注入した値は全て奥付ページに出る**。一つのテンプレートで使うつもりで注入した値も載るので、docs に明記する。

#### 背景: 外した案

- **データ層に流す（`__build_info` としてシステム定義エンティティ化）** — 機構としては成立する。`__definition` に先例があり（`schema_inspector` が preprocess で `__builtin/__definition.json` を吐き、views が `from: __definition.entities` で読み、`__data` にも tap にも乗る）、同じ経路に `__build_info` を足せる。tap から覗ける・`__data` 診断に自動で乗る・views から join できる、という利点も実在する。外した理由は 2 つ。(a) **views の出力が実行環境で変わるようになり、これは一方通行**。views が読めるようにした後で取り上げると利用者の views が壊れる。逆向き（奥付方式から後で data 層へ移す）は余地が残る。(b) **ビルド失敗ページに届かない**。preprocess で吐く以上、上流で失敗すれば reconcile からは見えず、奥付を出す 2 か所（表紙・失敗ページ）の片方が原理的に成立しない。なお views から build info を読みたい用途は現時点で無い
- **tap に provenance を載せる** — 上の代替として検討したが作らない。tap 出力は差分を取る使い方が主なので、毎回動く値が混ざると実質的な差分がノイズに埋もれる。守る線は「ソースだけで決まる」ではなく **「マシンと起動のしかたには依存しない」**（tap 出力には既に `__definition` 等のツール生成目録が乗っており、ツール版には依存している）。将来必要になったら、置き場はドキュメントの中ではなく外（`BuildResult` か隣接ファイル）
- **関数ではなくマッピングをグローバル登録する（`build_info["vars.git_sha"]`）** — 添字アクセスの不在は undefined になるので `| default()` がそのまま効く（実測）。外した理由は 2 つ。Python の dict のメソッドがテンプレートに漏れる（`build_info.items` が `<built-in method items>` を描く。`pycompat=False` で閉じたはずの穴）。任意の利用者テンプレートから全量を列挙でき、「列挙するのは奥付、キー照会するのは利用者テンプレート」という役割分担が崩れる
- **環境変数の素通し (`env.*`)** — テンプレートが環境の読み取り器になり、CI の環境（AWS クレデンシャル等）を出力に焼き込める。[60-template-trust-model.md](60-template-trust-model.md) の閉じた値モデルに穴を開けるため不可。越境するのは実行者が env / `--var` / MCP で明示的に差し出した値だけ
- **属性アクセス（`build.vars.commit` 等のコンテキスト注入）** — スキーマが保証するフィールドの顔になる。この情報はツール・実行環境依存で取得無保証の Optional であり、「文字列キーによる照会」という構文自体にその性格を語らせる。データ名前空間への予約名追加も不要になる（予約されるのは関数名一個 — `node` と同じ扱い）
- **汎用フィルタでの照会（`child` 等）** — 汎用語彙は record を通貨とするため `.value` の一段が常に付き、`child` の未解決は MissingNode として目立つ（「未設定が正常」な Optional には逆向き）。既存の `child` は id 照会フィルタとして今回の検討と独立に有用（実装・文書化済み）
- **関数名の別候補** — `mood.*`（ツール名を語彙に入れない — P4 `mood_view` → `render` と同じ裁定）、`build_context`（docs 既定義の「Template context」と概念衝突）、`env`（素通し期待を招き、慣習上の二義 — OS env 素通し / 実行モード — のどちらでもない）、`provenance`（裸名詞に錨が無い）。`build_info` は三名前空間すべてを「このビルドという出来事についての事実」として束ねる唯一の錨

#### 実装スコープ — PR の並び

1 PR ずつ独立して確認できる形に刻む。並びの原則は、**利用者から見える面を持たない土台を先に置き、供給チャネルを後から足す**こと。#1（関数・ストア・`processor.*` の 3 キー）、#2（奥付・`docs/` 公開・showcase 実例）、#3（奥付の独立ページ化・`processor.command`）、#4（config → ストアの経路）は実装済み。

| # | 内容 | store に増えるキー |
|---|---|---|
| 5 | vars — `ProjectConfig.vars` + env チャネル | `vars.*` |
| 6 | CLI `--var` + MCP `build` の `vars` | — |
| 7 | `manifest.*`（dotted 平坦化・`Manifest` に生 mapping 保持） | `manifest.*` |

- #5 の着手前に env の綴りを決める（[20-config-spec.md](../20-app/20-config-spec.md) の Proposals）
- #7 を最後に置いたのは、`manifest.*` が他のどれの前提でもないため。`Manifest` が生 mapping を保持する形に変わるので、レビューの観点も他と違う
