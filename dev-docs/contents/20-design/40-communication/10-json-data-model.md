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

### カタログのドット名構造化 (M12)

データカタログの `Attribute.id` に現れるドットには二つの意味がある:

1. **singleton 平坦化**: エンティティ内の単一オブジェクト属性は、wrapper エッジ（`item_type`, type=object, 子なし）+ ドット名エッジ（`item_type.id` 等）に展開される。データ上は入れ子
2. **リテラルキー**: view の alias（`select` の `as:`、`grouped` の `by:` の持ち出し等）がドットを含むと、そのままレコードのキー名になる。データ上は平坦

この二つはカタログ上区別できない（実証済み: `select` で `item: item_type.metadata, as: a` + `item: id, as: a.b` とすると、schema 由来の singleton 平坦化と同じ姿のカタログになるが、データは `{"a.b": ...}` という平坦キー）。原因は入口の非対称: schema.yaml は propertyNames が識別子パターンを課すためドット名は必ず平坦化由来だが、view-schema の alias 群は無制約。

実害: (1) tap 出力に jq でクォートの要るキーが生まれ得る、(2) entity_def.md が「入れ子」と「リテラル」を同じ見た目で表示、(3) カタログから JSON Schema を生成できない（J5 の前提）。

**案**: `Attribute` / `Edge` に `parent_attribute: str | None` を追加する（`Entity.parent_entity` と対称）。singleton 平坦化で生まれたエッジは吸収元 wrapper の名前を持ち、リテラルキーは None。`id` のドット表記は残す（`pluck` / `item:` / `by:` のアドレス表記であり、追加であって改名ではない）。

生成点は三箇所 + 自己記述:

- `schema_tree._collect_edges` — singleton 吸収時に親名を設定
- `query.SelectItem.derive` / `Flatten.derive` — ドット名の f-string 組み立てを構造的な設定に置き換え
- `query.Grouped.derive` — `by:` のエッジ持ち出し時は wrapper が消えるので None に落とす（リテラル化。データの実際の形と一致）
- `Entity.catalog` / `Attribute.catalog` の自己記述にもエッジ宣言を追加

却下した代替案: view alias に識別子パターンを課す。`grouped` の `by:` はドットパスを受けるのが仕様で、その出力キーのリテラルドットは塞げない。名前の文字列解析で構造を復元する危うさも残る。

### ルート Entity の導入 (M13)

フラットカタログ（Entity の列）にルートオブジェクト自身を表すレコードが無い。`collect_entities` はトップレベルの非 collection を黙って落とすが、schema-schema はトップレベルに singleton object / scalar / scalar array をすべて許し、データは normalize → compose → tap / テンプレートまで素通しする。結果、「データは存在するのに view からは `unknown source`、カタログ・meta ページには不可視」という三層のねじれがある（実証済み）。しかも singleton object は docs/reference/schema.md が「Single-record pattern」として三パターンの一つに数える正規の書き方であり、この穴はエッジケースの濫用ではなく文書化済み機能の不可視性である。`__definition` 自身も同じ穴にいる: `__definition.entities` というルートレベルのドット付き id が親無しでぶら下がり、`__definition` の下に入れ子であることを示す情報がカタログに無い。

**案**: 予約 id（`__root` 等。`__` 接頭辞はユーザ名から保護済み）でルートの Entity を一件 emit し、`item_type.attributes` にトップレベルの全キーを載せる:

- collection → `object[]` + `child_entity`（従来どおり）
- singleton object → wrapper + ドット名エッジ（エンティティ内と同じ吸収規約。M12 の `parent_attribute` に乗る）
- scalar / scalar array → 通常の属性（`child_entity` なし）
- `__definition` も `__root` の属性として正規化される

波及として決める点:

- `__entity_defs` / `__data` / `__entity_tree` は `__definition.entities` を filter する view なので、`__root` レコードの表示方針（除外か、index の情報源への昇格か）
- `from:` が singleton を指した場合のエラーを「unknown source」から「collection ではない」に改善できる
- `check_xref_coherence` の `parent_entity is None` フィルタから `__root` を除外

依存: M12 → M13 の順（singleton 吸収の表現が M12 の構造化に乗るため）。

### tap ドキュメントの JSON Schema 提供 (J5)

`mood tap` の data.json はテンプレートに流し込まれるルートオブジェクトそのものであり、その JSON Schema は tap 消費者（typegen・検証）とテンプレートを書く LLM の両方に効く。データからの探索と違い、レコード 0 件のエンティティ（キーごと消える）や absent な任意項目も語れる。

**案**: `components/shared/json_schema.py` に純関数を置く:

- `document_schema(entities) -> Mapping` — data.json 全体のスキーマ
- `entity_schema(entity_id, entities) -> Mapping` — 単一エンティティの断片（子孫を入れ子展開）

変換の要点: ドット名の入れ子復元（M12 の `parent_attribute` 前提）、ルートの合成（M13 の `__root` 前提）、`[]` 接尾の再帰的な `items` への展開、`validation` / `metadata` キーの素通し移送。

提供口は未決（tap データ本体には混ぜない — インタフェース分離）。候補: `__db/` メタ面への埋め込み（entity_def.md / view_def.md / 全体スキーマページ）、`mood tap --schema`、MCP ツール。導線（docs / MCP ツール記述）とセットで初めて使われる点に注意。

その他の論点: レコード 0 件エンティティのキー欠落と required 方針、`additionalProperties: false` の採否。

**着手トリガー**（いずれかが発生するまで保留）: (a) エージェントが tap データやテンプレート執筆で実際につまずく事例が出る、(b) SBOM 等で外部 JSON との型突き合わせが必要になる、(c) 利用者からスキーマ / typegen の要望が来る。前提タスク: M12, M13。
