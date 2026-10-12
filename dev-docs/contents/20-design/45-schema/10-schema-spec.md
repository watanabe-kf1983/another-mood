# Schema Specification

## External Design

### JSON Schema のサブセット

`definition/schema.yaml` は JSON Schema draft 2020-12 のサブセットで書く。削る基準は一つで、**スキーマを検証規則ではなくデータモデルとして読める形に保つ**こと（[データモデルの制約](../../10-concept/10-product.md#データモデル-規律を与えた-json-の木)）。どの構文も entity と attribute に一つの形・一つの型で落ちる。記法と各キーワードの正本は `docs/reference/schema.md` で、本節はフルセットから何を削ったかだけを並べる（項目ごとの理由と、OpenAPI のスキーマモデルとの違いは[背景](../../90-appendix/20-design/45-schema/10-schema-spec.md)）:

- **単一ファイル・単一ルート** — `$ref` / `$defs` / `$id` などの参照・識別機構を持たない。スキーマの再利用は別スキーマに切り出してキー参照する
- **合成・条件を持たない** — `allOf` / `anyOf` / `oneOf` / `not` / `if` を持たない。型のバリエーションはスキーマ（= テーブル）を分ける
- **`$comment` を持たない** — YAML のコメント構文（`#`）で代替する
- **ルートに `additionalProperties: <schema>` を許さない** — このツールではそれはレコードの集合を意味し、ルートがレコードの集合では各 entity への入口の役目を果たせない
- **`type` は単一の文字列** — 配列形（`[string, "null"]`）と `null` 型を持たない
- **型の付かない領域を残さない** — 素の `type: object`、`items` の無い `type: array`、宣言した `type` に一致しないリテラルを弾く
- **`x-ref` を足す** — JSON Schema に無い参照整合性制約を拡張キーワードとして加える（後述）

### 参照整合性制約: x-ref

JSON Schema 本体の property 宣言に `x-ref` キーワードを置き、参照先を構造化形式 (`{ entity, attribute }`) で記述する。JSON Schema 2020-12 は未知キーワードを許容するので、純 JSON Schema としての妥当性は保たれる。Snowflake の宣言的 FK と同じアプローチで、最終的な data-level 整合性は **強制せず警告止め** とする。

利用者向けの記法・フィールド・制約・data-level 警告の挙動は `docs/reference/schema.md` の Entity references (x-ref) を正本とする。本節は背後の設計判断に絞る。

#### 書ける位置

プロパティ宣言の直下にだけ x-ref を書ける。さらに以下の制約がある:

- **`type: string` のプロパティのみ**。integer / number / boolean / object / array は meta-schema エラーで拒否
- `items:` 直下 (スカラー配列要素の FK) は meta-schema エラーで拒否

どちらの理由も[背景](../../90-appendix/20-design/45-schema/10-schema-spec.md#x-ref-の背景各論)。

#### 意味論: enum validation framing

参照整合性制約は本質的に **enum validation の動的版** — 「この値は target の集合 (辞書キーの集合 or 指定 attribute の値の集合) に属さねばならない」。この framing で全ケースを一貫的に説明できる:

- Required でない FK の値が省略されている → 適用すべき enum がない → 検査対象外
- 空文字列 → 単なる値、特別扱いしない (target の集合に `""` がなければ違反)
- 自己参照 (e.g. `genres.parent_id` → `genres`) → enum 集合に自身も含まれるだけ、特別ルール不要
- cycle 検出 / cardinality (1:N, N:M) → FK の責務外、別レイヤー
- 多重ターゲット → 当面サポートしない (値依存で参照先が変わるフィールドは `x-ref` を付けない、自由文字列扱い)

#### 実行モード: schema-level はエラー、data-level は警告

参照整合性違反は重大度の階層が異なる。schema-level の不整合は data の読み込み以前に build を止める。data-level は警告として常時検出・常時報告するが、build/watch を止めない (ページは正常レンダリング)。`--strict` フラグは「警告があれば exit non-zero」の意味のみを持つ (検査の ON/OFF ではない)。

x-ref target の許容範囲: ユーザスキーマで宣言された top-level entity と、内蔵 content schema が提供する top-level entity (`prose` / `blob`) のみ。カタログのメタデータ (`__definition.*`) は FK 参照の意味を持たないため target から除外する。

## Internal Design

### データカタログ

スキーマから抽出した entity と attribute の目録を**データカタログ**（以下カタログ）と呼ぶ。`inspect_schema` ステージが `schema.yaml` から起こして永続化し、以後のステージはスキーマを読み直さずカタログを読む: normalizer の x-ref 検査、query_deriver の `from:` 解決と派生 entity の生成、composer のクエリ評価、generator のメタドキュメント描画。内蔵 content schema（prose / blob）の entity も同じカタログに載る。

形は二つある。Node / Edge の木が正本で、Entity の列はその平坦な直列化（以下「カタログの直列化」）。木は query_deriver が部分木を付け替えるために要り、列はステージ間の受け渡しとメタドキュメントの走査に使う（`data_catalog.py`）。

カタログの各エントリは **Entity** と **ObjectType** の 2 階層で表現される。

- **Entity**: データツリー上の到達経路を表す identifier (`id` = access path)。クエリ DSL の `from:`、paging 設定、表示見出しに使う。例: `categories`, `categories.tasks`。アンカーパス（リンク用の実体パス）とは別概念で、こちらは [anchor-spec.md](../70-generator/30-anchor-spec.md) を参照
- **ObjectType**: Entity の中の 1 つの item の型 (`id`)。コレクションを 1 段降りるたびに `.item` を付加する path-based 名。FK 参照や型レベルの cross-reference に使う。例: `categories.item`, `categories.item.tasks.item`

Entity は自身の `item_type` フィールドを通じて ObjectType を保持する。

```yaml
properties:
  categories:                # Entity.id: "categories"
    type: object             # Entity.item_type.id: "categories.item"
    additionalProperties:
      type: object
      properties:
        tasks:               # Entity.id: "categories.tasks"
          type: object       # Entity.item_type.id: "categories.item.tasks.item"
          additionalProperties: { type: object, properties: { ... } }
```

シングルトン (record 形、すなわち `properties` + `additionalProperties: false`) は entity 化されない。シングルトン自身が `object` 型の attribute になり、配下のプロパティが `meta.owner` のようなドット名の attribute として親エンティティに載る。entity 化されるのは collection (`additionalProperties` / `items`) のみで、シングルトン配下の collection はドット名のパスで entity になる (`categories.meta.tasks`)。

カタログ / メタドキュメンテーション側での扱いは [meta-documentation.md](../75-meta-documentation/10-database-information.md) 参照。

## Proposals

### ルート Entity の導入 (M13)

#### ゴール

ルート直下に置いた各形の振る舞いを、record（collection の 1 item）の中に置いた同じ形の振る舞いに揃える。言い換えると、ルートオブジェクトを一件の record として扱う。

| 形 | record の中（As-Is） | ルート直下（As-Is） | ルート直下（To-Be） |
|---|---|---|---|
| collection（`users.orders` / `users`） | 親を `parent_entity` とする entity。`from:` では引けず、親から `flatten` で降りる。`__db/` では親の Entity / Data ページの中に出る | entity。`from:` で引け、`__db/` に Entity / Data ページが出る | 変更なし |
| singleton object（`users.profile` / `site_config`） | entity にならず、親 record の `object` 属性になる。配下の値は `profile.name` のようなドット名の属性として親に載り、`__db/` では親の属性表に出る | カタログに載らない。`from:` は `unknown source`、`__db/` のどこにも出ない | ルート record の `object` 属性。配下はドット名の属性として載り、`__db/` ではルート record の属性表に出る |
| singleton の中の collection（`users.profile.tags` / `site_config.items`） | 親を `parent_entity` とするドット名の entity `users.profile.tags`。`from:` では引けず、親から `flatten` で降りる。`__db/` では親のページの中に出る | カタログに載らない。`from:` は `unknown source`、x-ref の参照先に指定すると `not found` | ルート record を親とするドット名の entity `site_config.items`。ルート直下の collection と同じく `from:` で引け、x-ref で名指しでき、`__db/` の Entities にドット名で載って Entity / Data ページを持つ |
| scalar / scalar 配列 | 親 record の属性。`__db/` では親の属性表に出る | カタログに載らない。`from:` は `unknown source`（存在しないキーと同じ診断） | ルート record の属性。`__db/` ではルート record の属性表に出る |

normalize は既にこの対称性を持っている（ルート直下の singleton の中の map 形も `id` 付き配列になり、data.json のルートに出る）。揃っていないのはカタログと、カタログを読む view / x-ref / `__db/` である。

#### To-Be に伴う外部仕様

- **tap / テンプレート**: 変更なし。data.json のルートは従来どおり
- **view**: ルート直下の singleton の中の collection（`site_config.items`）を `from:` で名指しできる。`from:` がルート直下の singleton / scalar を指したときは、存在しないキーと区別して「collection ではない」と診断する
- **x-ref**: `entity:` に `site_config.items` を指定できる
- **`__db/`**: `site_config.items` は Entities にドット名で載り、ルート直下の collection と同じく Entity / Data ページを持つ。ルート record は index に Entities / Views とは別枠の節を持ち、Entity と同じく Definition / Data の二ページに割る。トップレベルの singleton / scalar が利用者に見える唯一の場所。Definition はルート record の属性表（collection 属性は entity / view のページへのリンク、singleton はドット名の属性、scalar はそのまま。種別の列で entity / view / singleton / scalar を区別する）、Data はルート record の値（collection は値を描かず、その source の Data ページへのリンク）
- **docs**: docs/reference/schema.md の Single-record pattern の「view から名指しできず `__db/` にページも出ない」を書き換える

#### 現状、ルートが record と違う扱いを受けている場所

行は揃える順に並べる。「扱いを合わせたときの波及」の列は、ルートの Entity を列に出した瞬間にその場所で起きること。先頭の二行は単独で潰せる。「schema の出どころ」「木 → 列」「列での親の表現」「列 → 木」「内蔵 `__definition`」の五行は一斉に壊れるので、一つの PR で揃える。以下これを**ルート Entity を列に出す PR** と呼ぶ。残りの三行は壊れず、この PR の後に一行ずつ潰せる。x-ref の参照先に `site_config.items` を許すのは「データ側の record の取得」と同時にするのがよいかもしれない: ルート Entity を列に出す PR では参照先集合から外したままにし、FK 検査の袋に入った時点で許す。ルート Entity を列に出す PR の前に、各行の As-Is（`from:` の `unknown source`、x-ref の `not found`、`__db/` にトップレベルの singleton が出ないこと）を fixture テストに固定しておく。

| 場所 | record の扱い | ルートの扱い | 扱いを合わせたときの波及 |
|---|---|---|---|
| **schema → 木**（`schema_catalog.build_catalog_node`） | record schema を一つの Node にする。singleton は wrapper Node、scalar は葉 Node として、全プロパティが子に揃う | 同じ。ルート schema も一つの Node になり、singleton / scalar も子に揃う | 何も起きない。`test_schema_catalog.py` の「トップレベルは collection に限る」という注記だけが古くなる |
| **メタページの行の取得**（`meta_templates.walk_entity`） | 親の行から属性 id を `pluck` して子の行に降りる | 先頭の一段だけ `From(name).apply` でラッパーから引く | 祖先の連鎖がルートから始まり、先頭段の `From` がラッパーにルートの名前のキーを見つけられず、全てのデータ表が空になる。先頭段が他の段と同じ `pluck` なら壊れない |
| **schema の出どころ**（`schema_inspector.inspect_schema`） | 一つの schema node から一つの Node を起こす | 利用者 schema、内蔵 content schema（prose / blob）、Python で組む `__definition` の三つを別々に列にして別ファイルに書き、`load_model` の連結で合流させる | 三つの出どころがそれぞれルートを出すと、連結後の列にルートが三件並ぶ。利用者の entity、内蔵の entity、`__definition.*` が同じ一件を親に持てるのは、三つを一つの Node に合成して起こしたときだけ |
| **木 → 列**（`schema_catalog.collect_entities` → `data_catalog.flatten_tree`） | record の Node を `flatten_tree` に渡す。singleton / scalar はドット名の属性として Entity に載り、collection の子は `child_entity` 付き属性と子 Entity になる | ルートの Node は `flatten_tree` に渡さない。entity を開く子だけを拾って子ごとに `flatten_tree` する。ルートの Entity は作られず、singleton / scalar とその配下はここで落ちる | ルートの Node をそのまま `flatten_tree` に渡すと、ルートの id が子の id の接頭辞になる（`users` が `<root>.users`）。ルートの `id` と `item_type.id` を何にするかがここで初めて要る |
| **列での親の表現**（`Entity.parent_entity`） | 子 entity は `parent_entity` に親の id を持つ | ルート直下の entity は `parent_entity` を持たない。「トップレベル」はこれで判定している: `build_tree` の `_children_of(None)`、`check_xref_coherence` の参照先集合、`data_fk_validator._build_target_index`、内蔵 view `__entity_defs` / `__data` の `parent_entity: { exists: false }`、`index.md` の合成辺の `if entity.parent_entity` | ルート直下の entity の `parent_entity` がルートの id になり、五箇所が同時に壊れる: `_children_of(None)` がルートだけを返して `from:` が全て引けなくなる、x-ref の参照先集合が空になって全ての x-ref がエラーになる、FK の値集合が空になって全ての FK 値が警告になる、`__entity_defs` / `__data` が空になって `__db/` から Entity / Data ページが消える、`index.md` が全 entity からルートへの合成辺を描く。`parent_entity` 無しは view だけになる。一方で `site_config.items` は親がルートになり、x-ref の参照先に数えられる |
| **列 → 木**（`data_catalog.build_tree`） | 自分の Entity record から復元する。属性から singleton / scalar の枝を戻し、`child_entity` 付き属性から子 Entity を引き当てて吊る | Entity record が無いので、`parent_entity` を持たない Entity を `object[]` の edge として吊った**仮想ルート** Node を都度作る。singleton / scalar の枝は無い | 仮想ルートの子がルート一つと view だけになる（上の行の `_children_of(None)` と同じ事象）。ルートの Entity record から復元した Node は、仮想ルートに無かった singleton / scalar の枝を持ち、view は query_deriver がその Node に従来どおり `object[]` の枝として吊る |
| **内蔵 `__definition`**（`schema_inspector._emit_definition_catalog`） | record の中の singleton の中の collection は、上の一般経路でドット名の子 Entity になる（`categories.meta.tasks`） | ルート直下の singleton `__definition` の中の collection は一般経路を通らず、`__definition.entities` / `__definition.views` というドット入り id の top-level Entity を Python で直接組み立てる。`__definition` の下にいるという構造はカタログに無い | 手組みの `__definition.*` は親を持たないのでルートの Node の枝にならず、`from: __definition.entities` を使う内蔵 view が全て壊れる。ルートの Node に `__definition` の枝が吊ってあるときだけ、一般経路で同じ id のまま出る |
| **source 名の解決**（`query.From.derive`） | record の中のパスは `Node.reach` でセグメントごとに降りる（`flatten` の `of:` 等） | source 名は `has_child` で edge 名と丸ごと完全一致させる。`__definition.entities` が引けるのは、上の手書きでその名前の edge が一本あるから | 壊れない。ルートの Node の枝名は従来の entity 名のままなので `from: users` は引ける。ただし `site_config.items` はまだ引けず、`from: site_config` も「collection ではない」でなく `unknown source` のまま。`_reject_source_name_conflicts` は entity id の集合で見るので、view 名と singleton 名の衝突を見逃す |
| **データ側の record の取得**（`content_normalizer._accumulate` → `data_fk_validator` / `data_id_validator`） | record の中の collection は、親の record から `child_entity` を辿って降りる（`_walk_records`） | ルート直下の collection は、各ファイルの top-level の list を集めて entity ごとの袋にする。singleton の中の collection はこの袋に入らず、x-ref の参照先にも参照元にもならない | 壊れない。ただし `site_config.items` は x-ref の参照先に数えられる（「列での親の表現」）のに record が袋に無いので値集合が空になり、それを参照する全ての値が警告になる。`site_config.items` の中の x-ref は従来どおり検査されない |
| **メタページ**（`meta.yaml` / `index.md` / `META_EDITION`） | `__entity_defs` / `__data` が Entity / Data のページを出す | ページが無い | ルートの id が `__` で始まれば、内蔵 view の `__` 除外が効いて `__db/` の見た目は変わらない。`site_config.items` は親がルートなので Entities に載り、Entity / Data ページを持つ（To-Be どおり）。ルート自身のページは依然として無い |

ルート Entity を列に出す PR に向けた仮決め（実装で問題が見つかれば見直す）:

- ルートの `id` は `__root`、`item_type.id` は `__root.item`。`__` で始まるので内蔵 view の `__` 除外がそのまま効き、`__db/` が変わらないまま表示の判断を「メタページ」の行まで先送りできる。利用者の entity 名と view 名は `__` を使えないので衝突しない
- ルートの属性に view を含める。`inspect_schema` が出したルートのカタログに query_deriver が view の属性を追記する。J5 が求める「tap のルートを映す」属性表はこれで得られ、J5 側に合成の仕事を持ち込まない。懸念: カタログはファイル別に書いて `load_model` の連結で合流させるので、素朴に追記すると `__root` の Entity record が二件並ぶ。追記の形（query_deriver が完全なルートを出し直す、読む側で同じ id の record を束ねる、等）は実装時に決める

進め方メモ（一歩ごとに本節を更新し、揃った行は表から消す）:

1. 各行の As-Is を fixture テストに固定する（`from: site_config` の `unknown source`、x-ref で `site_config.items` を指したときの `not found`、`__db/` にトップレベルの singleton が出ないこと）
2. 以降は表の順: 「メタページの行の取得」→ ルート Entity を列に出す PR（五行を同時に）→ 「source 名の解決」→ 「データ側の record の取得」→ 「メタページ」→ docs の同期

#### 依存

J5 は M13 を前提とする。

[E17 (合成ビュー)](../60-composer/10-query-dsl-spec.md#合成ビュー-e17) はトップレベル・シングルトンのカタログ表現を前提にするので、M13 は E17 の前段でもある。
