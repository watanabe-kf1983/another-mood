# 設定システム仕様

reqs-builder の設定システムの振る舞いを定義する。

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

| キー | 型 | デフォルト | 環境変数 | 説明 |
|------|-----|---------|----------|------|
| `model.schema.dir` | string | `./model/schema` | `RB_MODEL_SCHEMA_DIR` | スキーマ定義ディレクトリ |
| `model.data.dir` | string | `./model/data` | `RB_MODEL_DATA_DIR` | ソースデータディレクトリ |
| `model.queries.dir` | string | `./model/queries` | `RB_MODEL_QUERIES_DIR` | クエリ定義ディレクトリ |
| `presentation.templates.dir` | string | `./presentation/templates` | `RB_TEMPLATES_DIR` | テンプレートディレクトリ |
| `presentation.paging` | string | `./presentation/paging.yaml` | `RB_PAGING_FILE` | ページ分割設定ファイル |
| `output.normalized.dir` | string | `./output/model/normalized` | `RB_OUTPUT_NORMALIZED_DIR` | Normalizer の出力先 |
| `output.views.dir` | string | `./output/model/views` | `RB_OUTPUT_VIEWS_DIR` | Composer の出力先 |
| `output.documents.dir` | string | `./output/documents` | `RB_OUTPUT_DOCUMENTS_DIR` | Document Generator の出力先 |
| `output.rendered.dir` | string | `./output/rendered` | `RB_OUTPUT_RENDERED_DIR` | Document Renderer の出力先 |
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用（未実装） |
