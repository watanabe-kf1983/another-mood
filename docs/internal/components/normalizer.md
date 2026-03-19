# Normalizer

入力ディレクトリの種類ごとに独立したステージとして3回実行される。
各呼び出しの Input / Watch 対象は [pipeline.md](../pipeline/pipeline.md) を参照。

## 共通ロジック

### エラー伝播

Normalizer は処理の前に、検証用スキーマの検証結果（Watch 対象）にエラーが含まれるかを確認する。
エラーがあれば検証・正規化を実行せず、エラー情報を出力ディレクトリに伝播する。
schema / queries の Normalize ではツール内蔵スキーマを使うため、この確認は常に空振りとなる。

## schema の Normalize

1. `schemaDir` の *.yaml 読み込み → ツール内蔵 SchemaSchema で妥当か検証
2. additionalProperties パターンの正規化（辞書→配列 + id、再帰的）
3. `normalizedSchemaDir` に書き出し + 検証結果を出力

## contents の Normalize

1. `contentsDir` の *.yaml 読み込み
2. contents を `schemaDir`（生の JSON Schema）で型検証
3. 参照整合性チェック（--strict 時のみ、正規化前の生データに対して、警告として出力）
4. additionalProperties パターンの正規化（辞書→配列 + id、再帰的）
5. `normalizedContentsDir` に書き出し + 検証結果を出力

## queries の Normalize

1. `queriesDir` の *.yaml 読み込み → ツール内蔵 QuerySchema で構文検証
2. additionalProperties パターンの正規化（辞書→配列 + id、再帰的）
3. `normalizedQueriesDir` に書き出し + 検証結果を出力

## Technical Stack

### 現行 TypeScript 実装（参照実装）

- スキーマ検証: Zod
- YAML 処理: js-yaml
- ディレクトリハッシュ: folder-hash

### 次期版（実装言語未定）

Python / TypeScript のいずれかを選択する。決定は実装開始時に行う。

いずれの言語でも:
- ツールは YAML を読むだけ（CUD は AI が直接編集）のため、高度な YAML ライブラリ（ruamel.yaml 等）は不要
- 標準的な YAML パーサー（PyYAML / js-yaml）で十分

## アプリケーション構成（現行 TypeScript 実装）

```
src/
  commands/
    validate.ts         # reqs-builder validate
  core/
    hash.ts             # ディレクトリハッシュ計算
    source.ts           # ソースYAML読み込み・マージ
    schema-validator.ts # 参照整合性チェック
```
