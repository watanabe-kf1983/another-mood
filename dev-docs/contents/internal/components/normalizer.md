# Normalizer

contents / queries の入力ディレクトリごとに独立したステージとして2回実行される。
各呼び出しの Input / Watch 対象は [pipeline.md](../pipeline/pipeline.md) を参照。
スキーマの解析は SchemaInspector が担う（[architecture.md](../architecture.md) 参照）。

## 統一フロー

contents / queries の2ステージは同一の処理フローに従う:

1. **検証用スキーマ読み込み → マージ**: 検証に使うスキーマファイル群を読み込み、マージして検証用辞書を構築する
2. **対象ファイルごとに検証 → 正規化**: 各入力ファイルを検証用スキーマで検証し（`required` 含む）、additionalProperties パターンの正規化（辞書→配列 + id）を行う
3. **正規化済みデータをマージ → 制約検証**: 正規化済みデータを deep merge（配列は単純結合）し、id 重複チェックおよび FK 参照整合性チェック（`--strict` 時のみ）を行う
4. **マージ前のファイル単位で出力**: ステップ 2 の結果（正規化済み・マージ前）をファイル単位で書き出す。検証結果も出力する

### ステージごとの入力

| ステージ | 検証用スキーマ | 対象ファイル |
|---|---|---|
| contents | `schema_dir`（ユーザ定義スキーマ） | `contents_dir/*.yaml` ※ |
| queries | 内蔵 QuerySchema | `queries_dir/*.yaml` |

※ `contents_dir` には YAML・Markdown のほかにバイナリファイル（PNG, JPG 等）も配置される想定。バイナリファイルの正規化における扱い（パス解決、Composer への受け渡し等）は未決定。Phase 8 タスク [H1, H2](../../../phase8-tasks.md)（仕様確定 + 実装）。

## エラー伝播

Normalizer は処理の前に、inspect_schema_dir にエラーが含まれるかを確認する。
エラーがあれば検証・正規化を実行せず、エラー情報を出力ディレクトリに伝播する。
queries の Normalize ではツール内蔵スキーマを使うため、この確認は空振りとなる。

## ファイル単位出力の動機

正規化済みデータをマージせずファイル単位で出力する理由:

- **Markdown 散文の分離**: Markdown ファイルは内蔵 prose スキーマで正規化されるが、マージ後に出力すると全ファイルの body が1つの巨大な YAML に結合されてしまう
- **ファイル組織の保持**: ユーザが意図したファイル分割（学校別、機能別等）をそのまま後続コンポーネントに引き継げる
- **マージ責務の分離**: Composer / Generator がそれぞれの文脈で必要なマージを行う

## 正規化ルール

### additionalProperties パターン（辞書→配列変換）

`additionalProperties` を辞書パターンとして扱い、配列 + `id` フィールドに正規化する:

- `additionalProperties` がオブジェクトスキーマ → 辞書キーを `id` に、値オブジェクトのプロパティをそのまま展開
- `additionalProperties` が非オブジェクト型（`string`, `number` 等） → 辞書キーを `id` に、値を `value` フィールドに格納
- `properties` のみ → 固定構造のオブジェクト、そのまま
- 入れ子の `additionalProperties` も再帰的に正規化する

正規化後のデータ形状の例は [schema-spec.md](../../design/normalizer/schema-spec.md) を参照。

### id の位置づけ

additionalProperties パターンの辞書キーから生成される `id` は、辞書キーの出自情報であり、RDB の主キー（PK）ではない。

論理的には、オブジェクトに PK なるものは必要ない。Unique Key や Index はレコードの構造ではなく、制約として外部から宣言するもの。`id` は辞書キーの性質として暗黙にユニーク性が保証されるが、それは PK だからではなく、YAML の辞書キーが重複を許さないという性質に由来する。

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言は将来対応とする。Phase 10 タスク [D8, D9](../../../phase8-tasks.md)。

## 背景: スキーマファイル自体の正規化が不適切な理由

スキーマファイル（`schema_dir/*.yaml`）に対して汎用の辞書→配列正規化を適用し、その結果をメタドキュメンテーション（スキーマの可視化）に使う案を検討したが、不採用とした。

理由: SchemaSchema で正規化しても JSON Schema の構造キーワード（`additionalProperties`, `properties`, `items` 等）がそのまま残り、フィールド一覧等の情報に到達するために何段もネストを降りる必要がある。クエリやテンプレートから扱うには冗長すぎる。

スキーマの可視化や参照整合性チェックには、JSON Schema の構造を解釈してフラットな情報に変換する **SchemaInspector**（6-4）を使う。辞書→配列正規化（6-3）はコンテンツデータ向けの処理として Normalizer に残す。

## Technical Stack

- スキーマ検証: jsonschema
- YAML 処理: PyYAML（通常の読み書き）、ruamel.yaml（検証エラーの行番号解決用）

