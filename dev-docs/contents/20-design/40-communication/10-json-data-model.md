# JSON データモデル

## Internal Design

### 定義

YAML DSL やテンプレートエンジンが操作する対象は「JSON データモデル」（object / array / string / number / boolean / null で構成されるツリー構造）である。JSON というシリアライズ形式とは無関係で、YAML から読み込んだデータに対しても同様に動作する。

Normalizer から Document Generator まで、全コンポーネントがこのデータモデル上で一貫して動作する。

なお、「JSON データモデル」という用語に対応する正式な仕様は存在しない（XML には XML Information Set という W3C 勧告があるが、JSON にはそれに相当するものがない）。CBOR の RFC 8949 が "the JSON data model" という表現を使用しており、本プロジェクトでもこれに倣う。

YAML のデータモデルは JSON データモデルのスーパーセット（日付型、整数/浮動小数の区別、アンカー等）だが、このアプリで扱うデータは JSON データモデルの範囲内に収まる。

### シリアライズ形式

コンポーネント間で YAML ファイルとしてデータを受け渡す際のシリアライズ仕様は **YAML 1.2** とする。

理由:

- ブール値が `true`/`false` のみに限定される。1.1 で問題になる `yes`/`no`/`on`/`off` の意図せぬブール化（通称 Norway 問題: `country: NO` がブール `False` になる）を回避できる。
- 全ての JSON ドキュメントが valid YAML 1.2 ドキュメントとなる。テストフィクスチャ等で JSON 互換の YAML を扱いやすい。
- ruamel.yaml の既定が 1.2。`version` 指定が不要。

パイプライン内部の中間ファイルは外部ツールから直接読まれない前提なので、PyYAML の 1.1 既定との互換性は要件にしない。

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

### ステージ間中間表現を JSON へ (M10)

前提の [M11](node:/tasks/M/tasks/M11)（入力形式に JSON を追加）は完了済み。[D11](node:/tasks/D/tasks/D11)（非 JSON 値の侵入経路を塞ぐ）は前提ではなかったが、こちらも完了しているので、中間表現に非 JSON 値が到達しえない状態から着手できる。

#### 対象範囲

このプロジェクトの YAML は 3 系統ある。JSON へ差し替えるのは (3) のみ。

| 系統 | 例 | 扱い |
|---|---|---|
| (1) ユーザ入力 | `contents/*.yaml`、`contents/*.json`、`definition/schema.yaml`、`reports.yaml`、`sbdb.yaml` | 現状のまま（`parse_mapping`。位置情報タグ付けが要る） |
| (2) 内蔵スキーマリソース | `resources/schemas/*.yaml` | YAML のまま（手書き・コメント付き。5 ファイル） |
| (3) ステージ間中間表現 | tmp 配下の各ステージ出力、`__build_report` | **JSON へ** |

#### `json_data_model` の API 分割

現在 `load_model` が (2) と (3) の両方を担っている。形式が分かれるので関数も分ける:

- `load_model(*paths)` / `save_model(path, data)` — 中間表現（JSON）
- `load_schema(*paths)` — JSON Schema ドキュメント（YAML）の読み込みと deep-merge。呼び出しは 5 箇所（schema-schema / view-schema / manifest-schema / reports-schema / content-schema + ユーザ schema.yaml のマージ）

シリアライズ設定は `json.dumps(..., ensure_ascii=False, indent=2)`。`_drop_nones`（nullable は項目自体を省略）は維持。literal block scalar の規約は JSON に存在しないので削除する — 複数行文字列は `\n` エスケープの 1 行になり、post-mortem 時の可読性が下がるのが主な代償。

#### 着手時の確認事項への回答

- **(a) 正規化は temp へ書く前に検証しているか** — している。`iter_normalized` は `check(src_dir, schema)` を全ファイル分先に回してから yield するので、`json.dumps` が先に落ちて診断が失われる経路はない
- **(b) スキーマ内の自由形式領域に日付が書けるか** — 書けない。D11 でスキーマ言語から型無制約の領域を無くした（[schema-spec](../50-normalizer/20-schema-spec.md#型の付かない領域を残さない)）ので、`inspect_schema` の `json.dumps` に非 JSON 値が届く経路は残っていない

#### 計測 (baseline)

dev-docs の `mood build` 実測 2.52 / 2.64 / 2.66 s。cProfile 下（総 6.07 s）の内訳:

| 経路 | cumtime | 呼び出し |
|---|---|---|
| 中間表現 read（`_load_mapping`） | 2.39 s | 120 |
| 中間表現 write（`save_model`） | 0.90 s | 60 |
| ユーザ入力 read（`parse_mapping`） | 0.52 s | 13 |

差し替え対象は上 2 行の 3.3 s（プロファイラ倍率込みで総時間の 54%）。実測は build report の `StageResult.timestamp` 差分でも取れる。

#### コミット粒度

1. `load_model` / `load_schema` の分割（YAML のまま、振る舞い不変の純リファクタ）
2. 中間表現を JSON へ（`load_model` / `save_model` + テスト追随 + 設計文書同期 + 計測結果）

### 未決事項

- **トップレベルスキーマが `type: array`（additionalProperties でない）の場合**: id を持たない配列のマージ・重複検出をどうするか未定
- **スキーマ名重複**: 複数スキーマファイルに同じトップレベルキーがあった場合の扱い（エラーとする想定だが未確定）
