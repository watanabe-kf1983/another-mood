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
