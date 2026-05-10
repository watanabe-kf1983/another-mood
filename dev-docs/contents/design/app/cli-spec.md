# CLI 仕様

## External Design

### 処理対象ディレクトリ

- CWD 配下のパスのみ許可。CWD 外のパス（`../other-repo/docs` 等）はエラーとする
