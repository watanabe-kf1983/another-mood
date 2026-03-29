# Normalizer

入力ディレクトリの種類ごとに独立したステージとして3回実行される。
各呼び出しの Input / Watch 対象は [pipeline.md](../pipeline/pipeline.md) を参照。

## 統一フロー

schema / contents / queries の3ステージは同一の処理フローに従う:

1. **検証用スキーマ読み込み → マージ**: 検証に使うスキーマファイル群を読み込み、マージして検証用辞書を構築する
2. **対象ファイルごとに検証 → 正規化**: 各入力ファイルを検証用スキーマで検証し（`required` 含む）、additionalProperties パターンの正規化（辞書→配列 + id）を行う
3. **正規化済みデータをマージ → 制約検証**: 正規化済みデータを deep merge（配列は単純結合）し、id 重複チェックおよび FK 参照整合性チェック（`--strict` 時のみ）を行う
4. **マージ前のファイル単位で出力**: ステップ 2 の結果（正規化済み・マージ前）をファイル単位で書き出す。検証結果も出力する

### ステージごとの入力

| ステージ | 検証用スキーマ | 対象ファイル |
|---|---|---|
| schema | 内蔵 SchemaSchema | `schemaDir/*.yaml` |
| contents | `schemaDir`（ユーザ定義スキーマ） | `contentsDir/*.yaml` ※ |
| queries | 内蔵 QuerySchema | `queriesDir/*.yaml` |

※ `contentsDir` には YAML・Markdown のほかにバイナリファイル（PNG, JPG 等）も配置される想定。バイナリファイルの正規化における扱い（パス解決、Composer への受け渡し等）は未決定。

## エラー伝播

Normalizer は処理の前に、検証用スキーマの検証結果（Watch 対象）にエラーが含まれるかを確認する。
エラーがあれば検証・正規化を実行せず、エラー情報を出力ディレクトリに伝播する。
schema / queries の Normalize ではツール内蔵スキーマを使うため、この確認は常に空振りとなる。

## ファイル単位出力の動機

正規化済みデータをマージせずファイル単位で出力する理由:

- **Markdown 散文の分離**: Markdown ファイルは内蔵 prose スキーマで正規化されるが、マージ後に出力すると全ファイルの body が1つの巨大な YAML に結合されてしまう
- **ファイル組織の保持**: ユーザが意図したファイル分割（学校別、機能別等）をそのまま後続コンポーネントに引き継げる
- **マージ責務の分離**: Composer / Generator がそれぞれの文脈で必要なマージを行う

## 正規化ルール

### additionalProperties パターン（辞書→配列変換）

`additionalProperties` がオブジェクトスキーマの場合、辞書パターンとして扱い、配列 + id フィールドに正規化する:

- `additionalProperties` がオブジェクトスキーマ → 辞書パターン。`properties` に明示されたキーはそのまま残し、それ以外のキーを配列 + id フィールドに変換
- `properties` のみ → 固定構造のオブジェクト、そのまま
- 入れ子の `additionalProperties` も再帰的に正規化する

正規化後のデータ形状の例は [schema-spec.md](../../external/normalizer/schema-spec.md) を参照。

### id の位置づけ

additionalProperties パターンの辞書キーから生成される `id` は、辞書キーの出自情報であり、RDB の主キー（PK）ではない。

論理的には、オブジェクトに PK なるものは必要ない。Unique Key や Index はレコードの構造ではなく、制約として外部から宣言するもの。`id` は辞書キーの性質として暗黙にユニーク性が保証されるが、それは PK だからではなく、YAML の辞書キーが重複を許さないという性質に由来する。

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言は将来対応とする。

## Technical Stack

- スキーマ検証: jsonschema
- YAML 処理: PyYAML（通常の読み書き）、ruamel.yaml（検証エラーの行番号解決用）

