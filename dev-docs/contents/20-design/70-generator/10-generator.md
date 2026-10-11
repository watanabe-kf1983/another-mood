# Document Generator

## External Design

### レポート設定ファイル

> **[W4 dup]** ↔ reports-schema.yaml:3-8,41-56,64-70、edition.py:120-131 (a)、reports.md:25-43 (b) — 完全。案: 削除→docs。残すのは「profile ではない」「--edition を持たない」の判断

設定構文（form A の `file_per`、form B の `editions:` マップ）は `docs/reference/reports.md`、edition 名規則と form A / B の `oneOf` 検証は `resources/schemas/reports-schema.yaml` を正本とする。設計判断:

- **edition は同一 report の体裁違いの並行出力**で、当面の差は `file_per`（分割粒度）のみ。Markdown→HTML レンダリングは全 edition 同一で、別レンダラ・別フォーマットは持たない。
- 全 edition を 1 ビルドで横並び公開する — **環境で 1 つ選ぶ "profile" ではない**。"並列ビルド" は成果物が横並びに出る意で concurrency は持たず、単一 edition 選択（`--edition`）も当面持たない。
- form A は暗黙の単一 edition `default`。edition 名の検証は**ゆるく**（非空・最低 1 件・`__` 始まり禁止）に留め、出力セグメント化時に anchor_path と同じ IRI エスケープ（`Edition.dir_segment`、表示は raw のまま）で FS-safe にする。FS 固有のキツいエッジ（長さ・予約名等）はパス書き出し側の検査に委ねる。

### ページパスと出力ディレクトリ

> **[W4 dup]** 導出規則 ↔ edition.py:71-95 (a)、10-generator:31-35 (c)、template.md:118-122、reports.md:45-47 (b) — 完全。出力図 ↔ guides.md:70-81 (部分)。__db/__entity_defs ↔ edition.py:136-139、10-json-data-model 予約プレフィックス (部分)。build-report 層 ↔ generator.py、10-generator:66-68 (部分)。案: 導出規則の再述は削除 (generator.md へポインタ)。出力図と「2 種で捉える」は残す

ページパスの導出規則（anchor_path 由来、root は `index.md`、セグメントは anchor_path と同じ IRI エスケープを継承）は `PagingPolicy.page_path` が持ち、正本は [anchor-spec.md](30-anchor-spec.md#ページパスの導出)。`page_path` は **edition ルート相対**で、実ファイルは render が edition のマウント先を被せた `{outDir}/{edition}/{page_path}` に書き出す（form A は暗黙 edition `default`）。root の入口には薄い**表紙**（cover。edition ではなく一回 render）を置き、システム生成のメタ（DB の自己記述）は `__db/` マウントへ退避する:

```
{outDir}/
  index.md                                     ← 表紙（cover。H1=project 名 / Reports + Database Information）
  default/   (form B なら web/ print/)          ← ユーザ edition（report 本体）
  __db/                                        ← DB 自己記述（メタ edition のマウント先）
    index.md                                     メタ index（ER 図・entity/view 一覧）
    __data/  __entity_defs/  __view_defs/        診断（edition 横断・常に __db 内の同位置）
  __build_info/  __warnings/                   ← build-report 層（reconcile が置き、表紙末尾にリンクを append）
```

`__db` マウントと各アンカールート（`__entity_defs` 等）はどちらも `__` 始まりだが要求する事情は別レイヤ: `__db` は edition 名のユーザ空間（`__` 始まりは検証で禁止）との衝突回避、`__entity_defs` はグローバル node_map でのユーザ entity/view 名との衝突回避。ゆえに `__db/entity_defs` にはできず `__db/__entity_defs` になる（[予約プレフィックス](../40-communication/10-json-data-model.md#予約プレフィックス)）。診断系は `__db` 内で edition 横断・常に同位置。

出力は **deliverable（著者の reports）と DB 自己記述（`__db/`）の 2 種**で捉え、表紙で reports を前面・`__db/` を控えめな別エントリに置く。`__db/` を reports / edition の軸には混ぜない（自己記述面を「体裁違いのレポート」に誤ラベルさせないため）。`__build_info/`（奥付）と `__warnings/`（警告ページ）は reconcile の build-report 層で自己記述とは別軸ゆえ `{outDir}` 直下、リンクは表紙 `index.md` に append。

マウントはリンク解決に**透過**: リンク URL は page 相対（`node_href`）なので `{edition}/` や `__db/` のマウント接頭辞は効かず、各 edition / マウントは自己完結した相対リンクのサブツリーになる（[anchor-spec.md のリンク解決](30-anchor-spec.md#リンク解決)）。

### 奥付

> **[W4 dup]** ↔ generator.py:115-118 (ファイル境界)、workspace.py:69-81 (config 全量、workspace.*)、build_info.py:16-18,40-42 (行が無い/書式)、generator.py:84-87 (失敗ページ)、command.py:294-304 (a)、template.md:358-360 (b) — 部分〜完全。案?: 設計判断は design→残し、コード側コメント (workspace.py、build_info.py、generator.py) を一文に縮める

奥付はストアの全量を列挙する独立ページ (`__build_info/`) で、表紙 (`index.md`) からはリンク節 (`## Build Information`) だけが張られる。`__warnings/` `__db/` と同じ形で、表紙の節見出しは `Database Information` に倣った綴り（パスの綴りは関数名 `build_info` 側に揃える）。

**ファイル境界を分けるのは、利用者が公開対象から外せるようにするため。** 奥付が語るのはビルドした環境の事実（実行者が注入した値、sbdb プロジェクトの絶対パス等）で、出力を公開する利用者にとっては読者が「ビルドした人」ではなくなる。表紙に混ぜ込むと外す手段が無いが、ディレクトリが分かれていれば `__build_info/` 一つを除外指定するだけで済む。ビルド結果をコミットする利用者にとっても、毎回動くタイムスタンプで表紙が汚れなくなる（動かないタイムスタンプに意味はないので、差分が出ること自体は仕様）。

**除外機構はツールに持たせない。** 何を公開するかはデプロイ手段（rsync / `aws s3 sync` / CI）の仕事で、ツールが公開ポリシーのフラグを持ち始めると同種の要求が積み上がる。ツールが負うのは「一箇所にまとまっていること」だけ。`__warnings/` も同じ立場。

**表紙のリンク節に値は載せない。** 要約を載せると「どのキーが表紙に値するか」という裁定が復活し、下の非契約宣言と衝突する。

**config は選ばず全量載せる**（`processor.config.*`。`vars` だけは `vars.*` 側に出す）。奥付が答えるのは「この run はどう起動されたか」で、config はその問いそのもの。部分集合にすると「どれが有用か」というツール側の趣味判断になる。`host` / `port` のように build では効かないパラメータも並ぶが、run の種別は `processor.command` として同じページにある。

**行が無いことは「その run でそれが起きなかった」を意味する**（watch に `site_dir` が無いのは publish しないから）。空欄の行を置くと `build_info(key, default)` の `default` が効かなくなる。この読み方を守るため、config が語らない実効値は別のキーで出す（作業ディレクトリ → `processor.workspace.*`）。値の書式はツールが発明しない（時刻は ISO 8601 一本、bool は YAML 綴り）。

パスは絶対で載せる。`namespace_root` 相対の tail は MCP で `.` に潰れ、チャネルによって情報量が変わる識別子になる。ローカルパスが公開物に出ることは、上のファイル境界で受け止める。

**ビルド失敗ページだけは奥付を埋め込む。** 失敗ページを読むのは必ずビルドした人であり、失敗した出力を公開する利用者は居ない。診断が既に絶対パスを焼いているページでもある。

### build_info のキーの名前空間 — 出所で三分する

> **[W4 dup]** vars の綴り規則 ↔ template.md:358、cli.md:268-274 (b)、25-entrypoints/10-config-spec:27-29 (c)、50-release:51-53 (c) — 部分。案: 綴り規則は削除→docs (config-spec へポインタ)。非契約宣言は残す

| 名前空間 | 出所 | 例 |
|---|---|---|
| `processor.*` | 今回処理した処理系 | `processor.name`, `processor.version`, `processor.started_at`, `processor.command` |
| `vars.*` | 実行者の注入値（供給機構は [20-config-spec.md](../25-entrypoints/10-config-spec.md)） | `vars.git_commit_id` |
| `manifest.*` | sbdb プロジェクトの宣言 (sbdb.yaml) | `manifest.title`, `manifest.sbdb_version` |

注入ルートは `vars.*` にしか書けない。処理系の識別（`processor.name` / `version` / `started_at` / `command`）と `manifest.*` を外から偽装する経路は無い（`processor.config.*` は環境変数 `MOOD_*` でも決まるが、それは config の写しであって注入ではない）。環境変数の素通し（`env.*`）を作らないのも同じ線で、テンプレートが環境の読み取り器になると CI のクレデンシャル等を出力に焼き込めてしまう（[60-template-trust-model.md](60-template-trust-model.md) の閉じた値モデルに穴を開ける）。越境するのは実行者が明示的に差し出した値だけ。

`processor.*` / `manifest.*` のキー目録は `docs/` で**意図的に非契約**とし、「処理系が供給するもので、目録はバージョン間で変わりうる。奥付ページで確認せよ」と明言する（沈黙を暗黙の安定保証に読ませない）。release.md の feature / breaking 判定は「docs/reference の約束の集合」に基づくため、目録を約束しないことでキーの増減・改廃がリリース分類上の破壊にならない。

**`vars.*` はその例外**で、キーを決めるのは利用者。ツールが約束するのは綴りの対応規則（環境変数は封筒を剥がして小文字化、`--var` / MCP は書いたまま）と、**注入した値は全て奥付ページに出る**こと。一つのテンプレートで使うつもりで注入した値も載るので、docs に明記している。

### 背景: データ層には流さない

> **[W4 → appendix]**

build info をシステム定義エンティティ（`__build_info`）として preprocess から流す案は、機構としては成立する（`__definition` が先例で、views から join でき、`__data` 診断にも tap にも自動で乗る）。それでも採らない理由は 2 つ。

**views の出力が実行環境で変わるようになり、これは一方通行**。views が読めるようにした後で取り上げると利用者の views が壊れる。逆向き（奥付方式から後で data 層へ移す）なら余地が残る。もう一つは **ビルド失敗ページに届かない**こと。preprocess で吐く以上、上流で失敗すれば reconcile からは見えず、奥付を出す 2 か所（表紙・失敗ページ）の片方が原理的に成立しない。

同じ理由で tap にも provenance を載せない。tap 出力は差分を取る使い方が主なので、毎回動く値が混ざると実質的な差分がノイズに埋もれる。守る線は「ソースだけで決まる」ではなく **「マシンと起動のしかたには依存しない」**（tap 出力には既に `__definition` 等のツール生成目録が乗っており、ツール版には依存している）。

## Internal Design

### ノードメタデータ

> **[W4 dup]** 表 ↔ data_tree.py:29-163 の各 docstring (a, 完全。正本宣言付きで表を保持)。引用「直接触らせない」↔ data_tree.py:1-5、meta_templates.py:104-111、60-trust-model:114、10-json-data-model:63-66 (完全)。案: 表は削除→コード、残すのは「テンプレートは触れない、出口はフィルタ」の不変条件。引用は削除 (差分「meta に改名しない理由」は data_tree.py コメントへ)

Generator はロードしたデータを inert に詰め替えたうえで `wrap_tree` でラップし、各ノードにシステム由来のフィールドを注入する。テンプレートは元データを Mapping / Array として直接走査し、これらのフィールドには**触れない** — 必要な値はフィルタが取り出して渡す。

| フィールド | 対象ノード | 内容 |
|---|---|---|
| `_parent` | 全ノード | データツリー上の直近の親ノード |
| `_parent_record` | Mapping のみ | 最も近い Mapping 祖先（間の Array を 1 段飛ばす） |
| `_meta.anchor_path` | 全ノード | このノードのアンカーパス（[anchor-spec.md](30-anchor-spec.md)） |
| `_meta.fragment` / `_meta.stamps_anchor` | 全ノード | リンクの着地 fragment と `<a id>` 刻印の要否（由来型ごとの anchor strategy が決める） |
| `_meta.object_type_id` | 全ノード | スキーマ位置を表すカタログ形 ID（Array 要素は `X.item`、singleton は `X`、Array は `X.item[]`） |

> **[W4 → appendix]** (この引用段落)

> **背景: なぜテンプレートから直接触らせないか.** テンプレートエンジン (minijinja) は `_` 始まりの **Python 属性**を undefined にし、メソッド呼び出しは拒否する（データ側の `_` 始まりキーは通る）。`row["_meta"]` も `attr()` も同じく undefined になるので迂回路は無い。これはホスト側の内部にテンプレートを触らせないという信頼モデルの意図そのもので、押し戻す理由がない。
>
> かといって prefix を外して `meta` 等にはしない。ノードは dict / list のサブクラスで、テンプレートからの `row.meta` は getitem を先に引くため、データ側に `meta` キーがあると静かにそちらが勝つ。`_` prefix はまさにこの shadowing を防ぐためにあり、Python 側では load-bearing なまま残す。したがって prefix は据え置き、**テンプレートへの出口だけをフィルタに移す**。
>
> 実際の消費者はこれで足りる: テンプレートからの実需はメタテンプレートの診断テーブルが描くアンカーパス列 1 箇所だけで、それはメタテンプレート専用フィルタ `anchor_path`（ノード → 文字列）が担う。残りの `_parent` / `_parent_record` / `_meta.object_type_id` は `render` の subtree guard・`page_path`・アンカー合成が Python 側で読むだけで、テンプレートからは元々使われていない。

ラップ対象（id 無し Array 要素・ネスト Array は inert container のまま除外）、`_parent` / `_parent_record` の二系統セマンティクス、`anchor_path` / `_type_path` の `cached_property` による再帰合成（amortized O(depth)）、prose 例外といった厳密な規則は `data_tree.py` の docstring が正本。

### render ループ

> **[W4 dup]** ↔ generator.py:68-77,155 (a, 完全)。機構。案: 削除→コード、「メタを特別扱いしない」意図はコードコメントへ

`generate()` は 2 サーフェスを出す:

- **表紙**（`{outDir}/index.md`）— deliverable を列挙する root ランディング。**データモデルを描かない**単発 render（edition ではなく、reconcile の build-report ページと同類）なのでデータ edition ループの外。
- **データ edition**（メタ=`__db/` + ユーザ）— データモデルを描く。メタもユーザも同じ `Edition` 型なので**単一ループ**で回し、メタを特別扱いする分岐を持たない。

各 `Edition` の差分フィールド（`paging` / `name` / `templates_dir` / `root_template` / `extra_filters` / `mirror_blobs`）と render 本体は `edition.py` / `generator.render_edition()` の docstring が正本。`root_template` は当面 `index.md` 固定で、[Edition 別ルートテンプレート（将来）](#edition-別ルートテンプレート将来)の継ぎ目。

### 表紙の edition 列挙

> **[W4 dup]** ↔ resources/templates/cover/index.md:1-13、stages.py:130-131、meta/index.md:3 (a, 完全)。機構。案: 削除→コード。「__db/ を直書きしない」「project 名依存を 1 箇所に」はテンプレートのコメントへ

表紙はデータループと**同じ `editions` 集合**を受け取り、`Edition.is_system` で 2 セクションへ振り分ける。決定:

- **H1 は project 名**（manifest の `title`、無ければ `project_dir` の basename）。
- `## Reports` = 非 system（ユーザ edition）を列挙、`## Database Information` = system（メタ edition）へ 1 本リンク。
- `## Database Information` のリンク先は**メタ edition の `dir_segment` から導出**（`__db/` を直書きしない）ので、マウント名を変えても追従する。
- 着地する `__db/index.md` の H1 は固定 `# Database Information` — 表紙の同名セクションから同名ページへ着く導線を保ち、project 名依存を表紙 1 箇所に閉じ込める。

### meta 診断の分割

> **[W4 dup]** ↔ meta_templates.py:133-139 META_EDITION docstring (a, 完全)。案: 削除→コード。「別ページが要るならノードを一つ立てる」決定は残す

meta 診断ページ（`__entity_defs` / `__view_defs` / `__data`）の主題は **実データツリーノード**（`resources/views/` のビルトインビューが生む）で、分割は通常の[分割ルール](20-template-spec.md#分割ルール)そのもの。meta には利用者の `reports.yaml` が無いので paging は固定（`META_EDITION.paging`）。

> **決定: 別ページが要るならノードを一つ立てる.** 1 ノードは（データ位置で定まる）1 ページにだけ描かれる。同一 entity を Definition と Data の 2 ページに出すのに `__entity_defs` / `__data` の **2 ビュー＝2 アンカールート**を立てるのがこの実践 — 予約キーや fallback で 1 ノードを複数ページに割る手は採らない。

### Reconcile

> **[W4 dup]** ↔ 40-communication/index.md:21 (c, ほぼ同文)、10-architecture:46-47 (c)、generator.py:84-100 (a)、30-template-spec:49、40-paging:44,49 (c) — 完全。案: ここを正本、communication/index 側をポインタ化（index 側は W4 で処理済み）。末尾順序の理由は残す

Reconcile は Generator の直後に位置するステージで、「Generator の出力（あるべき姿）」と「上流から伝播してきた `BuildReport`（実際に何が起きたか）」を突き合わせ、ユーザに見せる最終出力を確定する役割を持つ。

- エラー無し: Generator の出力をそのまま reconcile の出力ディレクトリに通す（pass-through）
- エラー有り: Generator の出力を破棄し、内蔵の `build_report/build_failure.md` テンプレートでエラーページを `index.md` にレンダリングする

奥付は両方の分岐に付ける。失敗ページは表紙を置き換えるので、失敗時に読者が見る唯一のページになるため。表紙側で生成側（cover テンプレート）に build info を渡さないのは、末尾に何がどの順で並ぶか（**本文 → 奥付リンク → 警告リンク**）を Reconcile 一箇所で決めるため。

条件付きで現れる警告リンクを末尾に置くのは、**常設セクションの位置が警告の有無で動かない**ようにするため。奥付がページ末尾の表だった頃は「本の奥付」として最後が自然だったが、リンク節になった以上その理由は無い。

この分離により以下が成立する:

- Generator は「views を Markdown に変換する」純粋な責務に集中できる（エラー時の出力差し替えロジックを持たない）
- 下流の site / publish ステージは Reconcile の出力の単一視点を持てばよく、エラー時と正常時の分岐を知らなくてよい

#### 命名について

> **[W4 → appendix]**

「reconcile（突き合わせる）」は本リポジトリ独自の語ではなく一般的な英単語だが、ドキュメントビルダーの文脈では珍しい語であり、馴染みのある語が引き起こす意味の取り違えを避ける狙いで採用した。読み手はこの定義に立ち戻ることで、Reconcile ステージの責務を一意に把握できる。

### build_info のキーを足す場所 — `Workspace` の `build_info` property

> **[W4 dup]** ↔ workspace.py:60-85 (a, 部分〜完全)。機構。案: 削除→コード (design にしかない理由はコメントへ)

キーは `Workspace` が既に型付きで持っている値の平坦化なので、上流で組んで運ぶ形にはしない（同じ事実が二重に載る）。ただし `pipeline/` はカバレッジ計測対象外なので、平坦化そのものは `components/shared/` の汎用ヘルパに置く。property が持つのは「どのキーがどの源から来るか」だけ。

同じ理由で `manifest.*` も、`Manifest` の型付きフィールドをそのまま射影する（`ProjectConfig` には pydantic の `model_dump`、`Manifest` には `dataclasses.asdict`）。欄を足したときに射影側の登録漏れで奥付から静かに落ちることがなく、manifest スキーマがトップレベルを `additionalProperties: false` で閉じている以上、フィールドの集合は定義上ちょうど網羅的になる。生の mapping を別に抱える形は採らない — 型に落とせないのは `tools` だけで、他処理系の名前空間 `tools.<processor>` の中身はスキーマが無制約にしている部分なので `Mapping[str, object]` が正しい型。入れ子はストアの平坦化が dotted に潰す。

`processor.config.*` は config の写しで、実効値は混ぜない。ずれるのは作業ディレクトリだけ — `tmp_dir` 未固定なら config には無いが、使い捨てのディレクトリは実在する。これを `processor.workspace.*`（`root` / `temporary`）として分ける。内部エラーの run はこのディレクトリを post-mortem 用に残すので（`command._discard_workspace`）、奥付を埋め込むビルド失敗ページでは残存パスとして読める。`temporary` が要るのは、`root` が「消えた使い捨て」か「利用者が固定したディレクトリ」かで読み方が変わるため。

## Proposals

### Edition 別ルートテンプレート（将来）

edition ごとに異なるルートテンプレート（`index.md` 以外）を**利用者が `reports.yaml` で指定したい**需要（Web 版と印刷版でトップ構成を変える等）。**機構（`Edition` の `root_template` / `templates_dir` フィールドと `generate()` ループでの差し替え）は既にある**ので、残るは reports.yaml への設定露出（`root_template` エントリのパースと `load_editions` での反映）のみ。加算的拡張。
