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

理由: テンプレートは欠損したフィールドを何も描かない（[template-spec.md](../70-generator/20-template-spec.md#欠損値は何も描かない)）ので、フィールドが無いことがそのまま「描かない」になる。null を補完しても `None.child` のようなネストアクセスのエラーは防げず、`dict.get("key", {})` によるフォールバックも null が入ると効かなくなる。フィールドが存在しない方がテンプレート側で扱いやすい。

### 予約プレフィックス

JSON データモデル上のオブジェクトキーに、以下のプレフィックスを予約する。

| プレフィックス | 用途 | 例 |
|---|---|---|
| `_`（単一） | Generator がノードへ注入するメタデータ（[anchor-spec.md](../70-generator/30-anchor-spec.md#ノードメタデータ)） | `_parent`, `_meta` |
| `__`（二重） | システム内部フィールド（ユーザは直接扱わない） | `__build_report`, `__definition` |

`__` はトップレベルの entity 名・view 名・edition 名で拒否する（内蔵ソース、およびツール自身の出力 `__db/` 等と同じ名前空間を共有するため）。`_` は規約上の予約で、Generator のメタデータがユーザデータのキーを影にしないために置く。

内蔵 prose スキーマのキー名 `prose` はプレフィックスなしで維持する。ユーザ定義との衝突が問題になった場合は、設定によるキー名変更で対応する。
