# 設定システム仕様

reqs-builder の設定システムの振る舞いを定義する。

## パス解決ルール

CLI の第一位置パラメータ `<dir>` を基準にパスが解決される（[cli-spec.md](cli-spec.md) 参照）。

- **入力パス**: `<dir>` を基準に解決される（例: `<dir>/contents`）
- **出力パス**: CWD を基準に、`.reqs-builder/<dir>/` 配下に配置される（例: `.reqs-builder/<dir>/tmp/normalized/schema`）

環境変数や設定ファイルで明示指定した場合はそのパスがそのまま使われる。

## 設定の読み込み

### 優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル
3. 環境変数

### 設定ファイル（未実装）

- ファイル名: `reqs-builder.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

> **Note**: 現在はデフォルト値と環境変数のみ対応。設定ファイル読み込みは未実装。

### 環境変数

各設定項目に対応する環境変数は、設定スキーマの「環境変数」列を参照。

## 設定スキーマ

以下のデフォルト値における `<dir>` は CLI の第一位置パラメータを表す。

### 入力（ユーザ編集）

| キー | 型 | デフォルト | 環境変数 | 説明 |
|------|-----|---------|----------|------|
| `schemaDir` | string | `<dir>/definition/schema` | `RB_SCHEMA_DIR` | スキーマ定義ディレクトリ |
| `contentsDir` | string | `<dir>/contents` | `RB_CONTENTS_DIR` | ソースデータディレクトリ（YAML + Markdown） |
| `queriesDir` | string | `<dir>/definition/queries` | `RB_QUERIES_DIR` | クエリ定義ディレクトリ |
| `templatesDir` | string | `<dir>/definition/templates` | `RB_TEMPLATES_DIR` | テンプレートディレクトリ |
| `profilesFile` | string | `<dir>/definition/profiles.yaml` | `RB_PROFILES_FILE` | プロファイル設定ファイル（ページ分割戦略） |

### 出力（ユーザパイプライン）

| キー | 型 | デフォルト | 環境変数 | 説明 |
|------|-----|---------|----------|------|
| `normalizedSchemaDir` | string | `.reqs-builder/<dir>/tmp/normalized/schema` | `RB_NORMALIZED_SCHEMA_DIR` | schema の Normalizer 出力先 |
| `normalizedContentsDir` | string | `.reqs-builder/<dir>/tmp/normalized/contents` | `RB_NORMALIZED_CONTENTS_DIR` | contents の Normalizer 出力先 |
| `normalizedQueriesDir` | string | `.reqs-builder/<dir>/tmp/normalized/queries` | `RB_NORMALIZED_QUERIES_DIR` | queries の Normalizer 出力先 |
| `viewsDir` | string | `.reqs-builder/<dir>/tmp/views` | `RB_VIEWS_DIR` | Composer の出力先 |
| `outDir` | string | `.reqs-builder/<dir>/output` | `RB_OUT_DIR` | Document Generator の出力先 |
| `render.outDir` | string | `.reqs-builder/<dir>/render` | `RB_RENDER_OUT_DIR` | Document Renderer の出力先 |

### 出力（ツールパイプライン）

| キー | 型 | デフォルト | 環境変数 | 説明 |
|------|-----|---------|----------|------|
| `meta.outDir` | string | `.reqs-builder/<dir>/meta/output` | `RB_META_OUT_DIR` | メタドキュメンテーション Generator の出力先 |
| `meta.render.outDir` | string | `.reqs-builder/<dir>/meta/render` | `RB_META_RENDER_OUT_DIR` | メタドキュメンテーション Renderer の出力先 |

### その他

| キー | 型 | デフォルト | 環境変数 | 説明 |
|------|-----|---------|----------|------|
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用（未実装） |
