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

#### As-Is

ルート直下のキーの扱いが、層ごとに食い違っている（例は `users`: map 形、`users.orders`: その中の object 配列、`site_config`: singleton、`site_config.items`: その中の object 配列）:

| 層 | collection（`users`） | collection の中の collection（`users.orders`） | singleton object（`site_config`） | singleton の中の collection（`site_config.items`） | scalar / scalar 配列 |
|---|---|---|---|---|---|
| meta-schema | 許す | 許す | 許す（`rootSchema` が課すのは `type: object`・`properties` 必須・`__` 禁止だけ） | 許す | 許す |
| normalize → compose → tap / テンプレート | entity として流れる | entity として流れる | 値のまま素通し（`tap` のトップレベルキーに出る） | 親の値の一部として素通し | 値のまま素通し |
| カタログ（`collect_entities`） | Entity を emit | `child_entity` として emit | 黙って落とす | 親ごと落ちる（内側に降りない） | 黙って落とす |

結果、右三列では「データは存在するのに view からは `unknown source`、カタログ・メタページには不可視」というねじれが起きる。singleton object は docs/reference/schema.md が Single-record pattern として数える正規の書き方なので、これはエッジケースの濫用ではなく文書化済み機能の不可視性である。`users.orders` と `site_config.items` はスキーマ上は同じ object 配列なのに、親が collection か singleton かだけで可視性が分かれる。

内蔵の `__definition` は同じ形（singleton の中の collection）だが、別経路で可視になっている。`schema_inspector._emit_definition_catalog` が `__definition.entities` / `__definition.views` という**ドット入り id の top-level Entity** を Python で直接組み立てるので、カタログ上は `parent_entity` が無く、`__definition` の下にいるという構造を持たない。それでも `from: __definition.entities` が引けるのは `From.apply` がソース名をドットで割ってデータを掘るからで、メタテンプレートの `walk_entity` も子 id から親 id を前方一致で外して属性 id を得ている。つまり「ドット = 入れ子」を、カタログの構造ではなく文字列操作で辻褄合わせしている。

#### To-Be

JSON データモデルのルートオブジェクトを、データカタログ上はルート Entity の一件の record として扱い、「ルートは一件の record で、collection 形の属性が entity になる」をユーザ schema と内蔵の両方に対する唯一の規約にする。予約 id `__root` でルートの Entity を一件 emit し、`item_type.attributes` にトップレベルの全キーを載せる:

- collection → `object[]` + `child_entity`（従来どおり）
- singleton object → wrapper + ドット名エッジ（エンティティ内と同じ吸収規約）。内側の collection はエンティティ内の `categories.meta.tasks` と同様、ドット名のパスで `child_entity` になる（`site_config.items`）。ルートだけ禁止する理由は無く、E17 の文書ノードの器にもなる
- scalar / scalar 配列 → 通常の属性（`child_entity` なし）
- view → collection 属性。`child_entity` はその view（`view: true` の Entity）。data.json のルートには view の結果も top-level キーとして入るので、`__root` の属性はそれを含めて初めて data.json のルートの写しになる（J5 の前提）
- `__definition` も `__root` の属性として同じ規約で正規化する。`_emit_definition_catalog` の手書きは無くなり、`__definition.entities` は親を持つ

id を `__` 接頭辞にするのは、ユーザが schema.yaml でルートに名前を付ける場所が無く、ツールが割り当てる名前だから（`__definition` と同じ側）。ユーザ名との衝突も起きない。ルートに `additionalProperties: <schema>` を許さない制約はそのまま。

**`__db/` での見せ方**: `__root` を entity の列には混ぜない（`__entity_tree` / `__entity_defs` / `__data` の `__` 除外はそのまま）。entity 用テンプレートに流すと Type Diagram に全 entity がぶら下がり、index の ER 図の焼き直しになるため。代わりに **Root Object** 専用の Definition view / Data view とテンプレートを設け、Database Information（`__db/index.md`）に Entities / Views とは別枠の Root Object 節を置いてそこへ導線を張る。Definition ページは `__root.item` の属性表（collection 属性は entity / view ページへのリンク、singleton はドット名の属性、scalar はそのまま。種別の列で entity / view / singleton / scalar を区別する）、Data ページはルート record の値（collection は Data ページへのリンク）。トップレベルの singleton / scalar が利用者に見えるのはここ。

#### やること（波及）

- Root Object 用のメタ view（`__` 除外の外で `id: __root` を一件引く Definition view と、ルート record を引く Data view）とテンプレートを足し、index に Root Object 節を置く
- `from:` が singleton を指した場合のエラーを「unknown source」から「collection ではない」に改善する
- `check_xref_coherence` の `parent_entity is None` フィルタから `__root` を除外する
- ドットの文字列操作の整理: `__definition.entities` が `__root` の属性として入れ子になれば、`from:` をパスとして読む形にでき、`From.apply` と `walk_entity` の前方一致はどちらもカタログの構造から引ける

#### 依存

E14 とは独立に着手できる（ルート singleton の吸収は既に「ドット = 入れ子」の規約に乗っている）。J5 は両方を前提とする。

[E17 (合成ビュー)](../60-composer/10-query-dsl-spec.md#合成ビュー-e17) はトップレベル・シングルトンのカタログ表現を前提にするので、M13 は E17 の前段でもある。E17 の文書ノードは、ユーザの singleton と同じ形で `__root` の属性に入り、型 id・アンカーパス・Root Object ページへの表示はすべて M13 の規約に乗る。
