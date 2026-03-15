# Normalizer

## 処理フロー

1. model/schema/*.yaml 読み込み → JSON Schema として妥当か検証
2. model/data/*.yaml 読み込み
3. data/ を schema/ で型検証
4. 参照整合性チェック（--strict 時のみ、正規化前の生データに対して、警告として出力）
5. additionalProperties パターンの正規化（辞書→配列 + id、再帰的）
6. output/model/normalized/ に書き出し + 検証結果を出力

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
