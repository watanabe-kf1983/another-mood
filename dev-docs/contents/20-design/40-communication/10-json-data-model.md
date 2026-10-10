# JSON データモデル

## Internal Design

### 定義

YAML DSL やテンプレートエンジンが操作する対象は「JSON データモデル」（object / array / string / number / boolean / null で構成されるツリー構造）である。JSON というシリアライズ形式とは無関係で、YAML から読み込んだデータに対しても同様に動作する。

Normalizer から Document Generator まで、全コンポーネントがこのデータモデル上で一貫して動作する。

なお、「JSON データモデル」という用語に対応する正式な仕様は存在しない（XML には XML Information Set という W3C 勧告があるが、JSON にはそれに相当するものがない）。CBOR の RFC 8949 が "the JSON data model" という表現を使用しており、本プロジェクトでもこれに倣う。

YAML のデータモデルは JSON データモデルのスーパーセット（日付型、整数/浮動小数の区別、アンカー等）だが、このアプリで扱うデータは JSON データモデルの範囲内に収まる。

### シリアライズ形式

このプロジェクトが読み書きするファイルは 3 系統あり、系統ごとにシリアライズ形式が決まる。

| 系統 | 例 | 形式 |
|---|---|---|
| (1) ユーザ入力 | `contents/*.yaml`、`contents/*.json`、`definition/schema.yaml`、`reports.yaml`、`sbdb.yaml` | YAML 1.2 / JSON |
| (2) 内蔵スキーマリソース | `resources/schemas/*.yaml` | YAML 1.2 |
| (3) ステージ間中間表現 | tmp 配下の各ステージ出力、`__build_report` | JSON |

- YAML は 1.2 とする（(1) (2) に適用）。`yes`/`no` の意図せぬブール化を避け、JSON 入力を追加の parser なしに受けるため（[背景](../../90-appendix/20-design/40-communication/10-json-data-model.md#yaml-を-12-とする理由)）
- 中間表現は JSON とする（(3) に適用）。ビルド時間を ruamel.yaml の read/write が支配していたため。tmp 配下は外部契約ではないので、変更は内部に閉じる（[背景](../../90-appendix/20-design/40-communication/10-json-data-model.md#中間表現を-json-とする理由)）。非 JSON 値（日付等）の到達経路はスキーマ言語の側で塞ぐ（[schema-spec.md](../../90-appendix/20-design/45-schema/10-schema-spec.md#型の付かない領域を残さない)）

### 配列内オブジェクトのフィールド統一

Normalizer およびコンポーネントが出力する配列内のオブジェクトは、原則として全て共通するフィールドを持つ。ただし、nullable な項目（スキーマ上 `required` でない項目）は、値が存在しない場合はフィールド自体を省略する（null を補完しない）。

理由: テンプレートは欠損したフィールドを何も描かない（[template-spec.md](../70-generator/30-template-spec.md#欠損値は何も描かない)）ので、フィールドが無いことがそのまま「描かない」になる。null を補完しても `None.child` のようなネストアクセスのエラーは防げず、`dict.get("key", {})` によるフォールバックも null が入ると効かなくなる。フィールドが存在しない方がテンプレート側で扱いやすい。

### 予約プレフィックス

JSON データモデル上のオブジェクトキーに、以下のプレフィックスを予約する。

| プレフィックス | 用途 | 例 |
|---|---|---|
| `_`（単一） | Generator がノードへ注入するメタデータ（[generator.md](../70-generator/10-generator.md#ノードメタデータ)） | `_parent`, `_meta` |
| `__`（二重） | システム内部フィールド（ユーザは直接扱わない） | `__build_report`, `__definition` |

`__` はトップレベルの entity 名・view 名・edition 名で拒否する（内蔵ソース、およびツール自身の出力 `__db/` 等と同じ名前空間を共有するため）。`_` は規約上の予約で、Generator のメタデータがユーザデータのキーを影にしないために置く。

内蔵 prose スキーマのキー名 `prose` はプレフィックスなしで維持する。ユーザ定義との衝突が問題になった場合は、設定によるキー名変更で対応する。

## Proposals

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
- **穴は singleton 一段ぶん深いところにも開いている**: トップレベル singleton が丸ごと落ちるので、その内側の collection（`wrapper: {items: [...]}` の `items`）もカタログに現れない。データは素通しされるので、上のねじれが一段深い位置で同じ形に起きる。`__root` の属性として吸収するか、メタスキーマ側で書けなくするかを決める

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
