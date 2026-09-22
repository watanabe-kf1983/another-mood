# JSON データモデル

## Internal Design

### 定義

YAML DSL やテンプレートエンジンが操作する対象は「JSON データモデル」（object / array / string / number / boolean / null で構成されるツリー構造）である。JSON というシリアライズ形式とは無関係で、YAML から読み込んだデータに対しても同様に動作する。

Normalizer から Document Generator まで、全コンポーネントがこのデータモデル上で一貫して動作する。

なお、「JSON データモデル」という用語に対応する正式な仕様は存在しない（XML には XML Information Set という W3C 勧告があるが、JSON にはそれに相当するものがない）。CBOR の RFC 8949 が "the JSON data model" という表現を使用しており、本プロジェクトでもこれに倣う。

YAML のデータモデルは JSON データモデルのスーパーセット（日付型、整数/浮動小数の区別、アンカー等）だが、このアプリで扱うデータは JSON データモデルの範囲内に収まる。

### シリアライズ形式

このプロジェクトが読み書きするファイルは 3 系統あり、系統ごとにシリアライズ形式が決まる。

| 系統 | 例 | 形式 | 読み書き |
|---|---|---|---|
| (1) ユーザ入力 | `contents/*.yaml`、`contents/*.json`、`definition/schema.yaml`、`reports.yaml`、`sbdb.yaml` | YAML 1.2 / JSON | `parse_mapping` |
| (2) 内蔵スキーマリソース | `resources/schemas/*.yaml` | YAML 1.2 | `load_schema` |
| (3) ステージ間中間表現 | tmp 配下の各ステージ出力、`__build_report` | JSON | `load_model` / `save_model` |

**YAML を 1.2 とする理由** ((1) (2) に適用):

- ブール値が `true`/`false` のみに限定される。1.1 で問題になる `yes`/`no`/`on`/`off` の意図せぬブール化（通称 Norway 問題: `country: NO` がブール `False` になる）を回避できる。
- 全ての JSON ドキュメントが valid YAML 1.2 ドキュメントとなる。(1) で JSON 入力を受けるのに追加の parser を要さない。
- ruamel.yaml の既定が 1.2。`version` 指定が不要。

**中間表現を JSON とする理由** ((3) に適用):

ビルド時間のうち ruamel.yaml が支配的だったため。差し替え前の `mood build dev-docs` は 2.67 s、うち中間表現の read/write が cProfile 下で 3.3 s（総 6.07 s の 54%）を占めていた。JSON へ差し替えた後は 1.79 s。tmp 配下は外部契約ではないので、変更は内部に閉じる。

PyYAML の CSafeLoader/Dumper (libyaml) なら YAML のまま 15 倍速くなるが採らない。PyYAML は YAML 1.1 なので、上記の 1.2 を選んだ理由がそのまま失われる。JSON はその曖昧さが構造的に無い。pickle / marshal も計測したが load はほぼ同速（差は 1 ms 未満）で、可読性を失うだけ。

代償は複数行文字列の可読性。YAML の literal block scalar に相当する規約が JSON に無いため、`\n` エスケープの 1 行になり post-mortem 時に読みにくい。`indent=2` と `ensure_ascii=False` で構造と非 ASCII 文字の可読性は保つ。

中間表現に非 JSON 値（日付等）が到達すると `json.dumps` が `TypeError` を投げる。到達経路はスキーマ言語の側で塞いである（[schema-spec.md](../50-normalizer/20-schema-spec.md#型の付かない領域を残さない)）。

#### ファイル名の規約

中間表現のファイル名は、元ソースの名前に `.json` を **追記** する（置換しない）。`foo.yaml` / `foo.yml` / `foo.json` / `foo.md` が同じ出力先に衝突しないようにするため。データカタログもこれに倣い、`schema.yaml` から `schema.yaml.json` を書く。

### 配列内オブジェクトのフィールド統一

Normalizer およびコンポーネントが出力する配列内のオブジェクトは、原則として全て共通するフィールドを持つ。ただし、nullable な項目（スキーマ上 `required` でない項目）は、値が存在しない場合はフィールド自体を省略する（null を補完しない）。

理由: Jinja2 のデフォルト設定では、未定義のフィールドへのアクセスはエラーにならず空文字として描画される。一方 null が入っている場合は `"None"` という文字列が描画されてしまう。また、null を補完しても `None.child` のようなネストアクセスのエラーは防げず、`dict.get("key", {})` によるフォールバックも null が入ると効かなくなる。フィールドが存在しない方がテンプレート側で扱いやすい。

なお、Generator がアンカーパス解決等のためにノードへメタ情報注入を行う仕組み（[generator.md](../70-generator/10-generator.md#ノードメタデータ) 参照）に、スキーマ情報に基づく未定義フィールドアクセスの検知（typo 検出）を相乗りさせて実現できる可能性がある。

### 予約プレフィックス

JSON データモデル上のオブジェクトキーに、以下のプレフィックスを予約する。ユーザ定義のフィールド名にこれらのプレフィックスは使用できない。

| プレフィックス | 用途 | 例 |
|---|---|---|
| `_`（単一） | 将来の拡張用に予約。現時点では使用箇所なし | — |
| `__`（二重） | システム内部フィールド（ユーザは直接扱わない） | `__build_report` |

`__` プレフィックスのフィールドはパイプライン基盤が使用し、ユーザのテンプレートやクエリからは参照しない。`_` プレフィックスは将来ユーザ空間とシステム空間が混在する場面に備えて予約する（Generator が注入する `_parent` / `_parent_record` / `_meta` 等、[generator.md](../70-generator/10-generator.md#ノードメタデータ) 参照）。

内蔵 prose スキーマのキー名 `prose` はプレフィックスなしで維持する。ユーザ定義との衝突が問題になった場合は、設定によるキー名変更で対応する。

### マージ戦略

実装は `json_data_model.py` の `deep_merge` を参照。

## Proposals

### 未決事項

- **トップレベルスキーマが `type: array`（additionalProperties でない）の場合**: id を持たない配列のマージ・重複検出をどうするか未定
- **スキーマ名重複**: 複数スキーマファイルに同じトップレベルキーがあった場合の扱い（エラーとする想定だが未確定）

### カタログの木を JSON データモデルと同形にする (M15)

#### 問題

カタログの `dc.Node` / `dc.Edge` は、singleton オブジェクトを**本物の子 Node ではなくドット名の兄弟エッジ**として持つ。`参照` (type=object、子 Node は空) と `参照.テーブル` / `参照.列` が同じ親の children に並ぶ形で、`schema_tree._collect_edges` が生成する。

この形はフラットカタログ (`Entity` / `ObjectType` / `Attribute`) の都合から来ている。`Attribute.id` は 1 本の文字列で、`Node.is_entity` は `bool(children)` で定義され、singleton は entity 化してはいけない。つまり平坦形は**直列化形の都合**だが、メモリ内表現である `Node` / `Edge` までそれに合わせてある。

結果、プロジェクト内に木の表現が四つ並び、平坦なのが二つある:

| 表現 | 形 |
|---|---|
| `schema_tree` の `ObjectNode` / `ArrayNode` / `ValueNode` + `SchemaProperty` | 入れ子 (スキーマの形) |
| `dc.Node` / `dc.Edge` | **平坦 + ドット** |
| `dc.Entity` / `ObjectType` / `Attribute` | 平坦 (直列化形) |
| `generator.data_tree` の `Node` | 入れ子 (JSON データの上) |

そして「ドット名 = singleton の入れ子」という規約を、次の八箇所が知っていなければならない:

- `schema_tree._collect_edges` — 平坦化を行う (生産側)
- `data_catalog._flatten_entity` — 「エッジ名自体にドットが入るので `edge_path` はタプルで保つ」
- `data_catalog._item_type_id` — 「単一エッジ名の中のドットは保存する」
- `query.Flatten.derive` — 要素をドット兄弟としてインライン化する
- `query.SelectItem.derive` — 接頭辞一致でドット兄弟を連れて行く
- `json_data_model.pluck` / `split_path` / `match_key` — longest-first 照合 (E15 で消える)
- `Attribute.catalog` / `Entity.catalog` — 平坦形を手書きし、コメントで規約を説明している
- `generator.data_tree._type_path` — ドット id を組み立ててカタログ表記に合わせる

#### 方針: singleton を子 Node にし、平坦化を境界に閉じ込める

`dc.Node` / `dc.Edge` を JSON データモデルと同形にする。singleton オブジェクトは `object` 型のエッジで到達する**本物の子 Node** になり、エッジ名からドットが消える。平坦化はシリアライズ境界の一対に閉じる:

| 関数 | 現在 | M15 後 |
|---|---|---|
| `schema_tree.to_catalog_node` / `_collect_edges` (schema → Node) | 平坦化する | **しない** (`ObjectNode` を子 Node として再帰) |
| `data_catalog.flatten_tree` (Node → Entity) | 何もしない | **入れ子 → ドット `Attribute.id` に平坦化** |
| `data_catalog.build_tree` (Entity → Node) | ドット id を `Edge.name` に写すだけ | **ドット `Attribute.id` → 入れ子 Node に復元** |

上の八箇所の規約は、この二関数だけが知っていればよくなる。

#### 背景: 一方向の変換を往復のペアにする理由

「平坦化が 1 箇所から 2 箇所に増える」ように見えるが、数えるべきはコード経路ではなく**規約を守らなければならない箇所**である。一方向だと曖昧な平坦形が唯一のメモリ内表現になるので、全生産者・全消費者が規約を守る必要がある (上の八箇所)。往復にすると曖昧さはワイヤ形式との境界に閉じ込められ、しかも `build_tree ∘ flatten_tree` の恒等性として機械的に検証できる。

この判断は E14 の実装着手時に露見した。書き込み先パスを平坦形に正規化する部品を作ると、ドット合成親と「同一の書き込みから出た親子」を運ぶフィールドが要る — **五つ目の表現形態**になり、レビューが成立しなかった。入れ子であればその部品は素朴なカタログの木の探索・挿入に収まる。

#### 着手前に決める点

- **`is_entity` の置き換え**: `bool(children)` では singleton が entity 化してしまう。`Edge.type` の `[]` 接尾で判定するか、エンティティ性を `Edge` 側の情報として持たせるか
- **配列跨ぎガードの置き場所**: 平坦形では `has_child` の完全一致だけで「ドットパスは singleton を通れるが配列は跨げない」が無料で成立していた ([走査の非対称性](../60-composer/10-query-dsl-spec.md#背景-走査の非対称性を設計原則として確立した))。入れ子では `Node` のパス探索に「`[]` エッジでは降りない」を明示する
- **`Attribute.catalog` / `Entity.catalog` の手書き ClassVar**: 入れ子で書き直す形

#### 検証

利用者から見た振る舞いは変わらない。直列化形が不変なので:

- `dev-docs` と `showcase/` 4 件のビルド出力がバイト一致 (`__entity_defs` / `__view_defs` / `__data` と全レンダリングページ)
- `build_tree(flatten_tree(node)) == node` の往復性 (平坦形が唯一の形である現在は自明に成立するので、テストを書く意味が初めて生まれる)
- 既存テストがそのままハーネスになる。`test_query.py` / `test_query_deriver.py` のフィクスチャは YAML の `Entity` 辞書から `dc.Entity.from_dict` → `dc.build_tree` で作られているため、直列化形を入口にしており影響を受けない。ドット名を直接アサートしている箇所は全テストで九箇所

#### 波及

- [E14](../60-composer/10-query-dsl-spec.md#ドット名の意味論統一-e14-e15) の前段。書き込み先パスの部品からドット合成親と兄弟の持ち回りが消える
- [M16](#スキーマ中間木の統合-m16) の前段
- `Attribute.id` のドットは直列化形にそのまま残る。J5 が読むのはこの平坦な `Attribute` の列なので、「ドットは必ず入れ子」という E14 の不変条件は M15 とは別に依然必要

### スキーマ中間木の統合 (M16)

#### 問題

`schema_tree` は JSON Schema から自前の三ノード木 (`ObjectNode` / `ArrayNode` / `ValueNode` と、辺に相当する `SchemaProperty`) を組み、`to_catalog_node` で `dc.Node` に変換する。この木は入れ子であり、[M15](#カタログの木を-json-データモデルと同形にする-m15) 後の `dc.Node` / `dc.Edge` とほぼ同型になる — `SchemaProperty` は `name` / `required` / 子 / `x_ref` を持ち、`dc.Edge` とほぼ同じ役割を担う。

`to_catalog_node` / `_collect_edges` は現在、この同型な木を平坦形に潰すために存在している。M15 後はほぼ恒等写像になり、中間木が要るのかという問いが立つ。

#### 案

`schema_tree` の三ノード木を落とし、JSON Schema から直接 `dc.Node` / `dc.Edge` を組む。判断が要るのは、両者で情報の置き場所が違う点:

- `ValueNode` は `type` / `validation` をノード側に持つが、`dc` では `Edge` 側にある
- `ArrayNode` の入れ子は `dc` では `Edge.type` の `[]` 接尾で表される (`string[][]` のような多段も文字列で表現される)
- `metadata` の優先規則 (「ArrayNode の metadata が勝つ — 外側の dict-pattern スキーマが型レベルの metadata を持つ」) をどこで表すか
- `UserStr` による位置情報の持ち回りが崩れないか

畳めないと判断した場合でも、`_collect_edges` の平坦化が消えた分の整理は残る。M16 は「畳めるかの見極めと、その結論に沿った整理」を範囲とする。

依存: M15 が前提。

### データキーにドットを含めない (E14)

view の別名スロット（`select[].as` / `flatten.as` / `join.as` / `grouped.by` 等）は現在、ドットを含む文字列をそのままレコードのキーにする。データにドット入りキーを生む経路はこれだけで、`contents/` 由来のキーは schema.yaml の識別子パターンで縛られている。このため `pluck` は longest-first 照合（キー全体を試してから末尾セグメントを削って降りる）を持ち、カタログの `Attribute.id` のドットは singleton 平坦化（入れ子）かリテラルキーか区別できない。

**案**: DSL の名前を読みも書きもパスとして統一し、データキーにドットを含めない不変条件を立てる。`pluck` は素朴な `split(".")` に戻し、カタログのドットは必ず入れ子を意味する（旧案の `parent_attribute` 追加は不要になる）。設計の本体は [query-dsl-spec.md](../60-composer/10-query-dsl-spec.md#ドット名の意味論統一-e14-e15)。実装後、不変条件はこのファイルの Internal Design に移す。

### ルート Entity の導入 (M13)

フラットカタログ（Entity の列）にルートオブジェクト自身を表すレコードが無い。`collect_entities` はトップレベルの非 collection を黙って落とすが、schema-schema はトップレベルに singleton object / scalar / scalar array をすべて許し、データは normalize → compose → tap / テンプレートまで素通しする。結果、「データは存在するのに view からは `unknown source`、カタログ・meta ページには不可視」という三層のねじれがある（実証済み）。しかも singleton object は docs/reference/schema.md が「Single-record pattern」として三パターンの一つに数える正規の書き方であり、この穴はエッジケースの濫用ではなく文書化済み機能の不可視性である。`__definition` 自身も同じ穴にいる: `__definition.entities` というルートレベルのドット付き id が親無しでぶら下がり、`__definition` の下に入れ子であることを示す情報がカタログに無い。

**案**: 予約 id（`__root` 等。`__` 接頭辞はユーザ名から保護済み）でルートの Entity を一件 emit し、`item_type.attributes` にトップレベルの全キーを載せる:

- collection → `object[]` + `child_entity`（従来どおり）
- singleton object → wrapper + ドット名エッジ（エンティティ内と同じ吸収規約）
- scalar / scalar array → 通常の属性（`child_entity` なし）
- `__definition` も `__root` の属性として正規化される

波及として決める点:

- `__entity_defs` / `__data` / `__entity_tree` は `__definition.entities` を filter する view なので、`__root` レコードの表示方針（除外か、index の情報源への昇格か）
- `from:` が singleton を指した場合のエラーを「unknown source」から「collection ではない」に改善できる
- `check_xref_coherence` の `parent_entity is None` フィルタから `__root` を除外

依存: E14 とは独立に着手できる（ルート singleton の吸収は既に「ドット = 入れ子」の規約に乗っている）。J5 は両方を前提とする。

[E17 (合成ビュー)](../60-composer/10-query-dsl-spec.md#合成ビュー-e17) はトップレベル・シングルトンのカタログ表現を前提にするので、M13 は E17 の前段でもある。合成ビューを `__root` の属性として吸収するか、view 同様に独立の項目として emit するかは E17 側で決める。

### tap ドキュメントの JSON Schema 提供 (J5)

`mood tap` の data.json はテンプレートに流し込まれるルートオブジェクトそのものであり、その JSON Schema は tap 消費者（typegen・検証）とテンプレートを書く LLM の両方に効く。データからの探索と違い、レコード 0 件のエンティティ（キーごと消える）や absent な任意項目も語れる。

**案**: `components/shared/json_schema.py` に純関数を置く:

- `document_schema(entities) -> Mapping` — data.json 全体のスキーマ
- `entity_schema(entity_id, entities) -> Mapping` — 単一エンティティの断片（子孫を入れ子展開）

変換の要点: ドット名の入れ子復元（E14 で「カタログのドットは必ず入れ子」が保証される前提）、ルートの合成（M13 の `__root` 前提）、`[]` 接尾の再帰的な `items` への展開、`validation` / `metadata` キーの素通し移送。

提供口は未決（tap データ本体には混ぜない — インタフェース分離）。候補: `__db/` メタ面への埋め込み（entity_def.md / view_def.md / 全体スキーマページ）、`mood tap --schema`、MCP ツール。導線（docs / MCP ツール記述）とセットで初めて使われる点に注意。

その他の論点: レコード 0 件エンティティのキー欠落と required 方針、`additionalProperties: false` の採否。

**着手トリガー**（いずれかが発生するまで保留）: (a) エージェントが tap データやテンプレート執筆で実際につまずく事例が出る、(b) SBOM 等で外部 JSON との型突き合わせが必要になる、(c) 利用者からスキーマ / typegen の要望が来る。前提タスク: E14, M13。
