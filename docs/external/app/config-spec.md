# 設定システム仕様

reqs-builder の設定システムの振る舞いを定義する。

## 設定の読み込み

### 優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル
3. 環境変数

### 設定ファイル（未実装）

- ファイル名: `stdg.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

> **Note**: 現在はデフォルト値と環境変数のみ対応。設定ファイル読み込みは未実装。

#### JSON形式の例

```json
{
  "output": {
    "doc": {
      "dir": "./build"
    }
  }
}
```

### 環境変数

各設定項目に対応する環境変数は、設定スキーマの「環境変数」列を参照。

## 設定スキーマ

| キー | 型 | デフォルト | 環境変数 | 説明 |
|------|-----|---------|----------|------|
| `source.dir` | string | `./source` | `STDG_SOURCE_DIR` | ソースディレクトリ |
| `toc.dir` | string | `./toc` | `STDG_TOC_DIR` | ToC定義ディレクトリ |
| `templates.dir` | string | `./templates` | `STDG_TEMPLATES_DIR` | テンプレートディレクトリ |
| `output.doc.dir` | string | `./output/docs` | `STDG_OUTPUT_DOC_DIR` | Generator の出力先ディレクトリ |
| `output.toc.dir` | string | `./output/tocs` | `STDG_OUTPUT_TOC_DIR` | レンダリング済みToC出力ディレクトリ（デバッグ用） |
| `output.rendered.dir` | string | `./output/rendered` | `STDG_OUTPUT_RENDERED_DIR` | レンダリング結果（HTML）の出力先ディレクトリ |
| `render.hugo.*` | object | `{}` | (なし) | hugo-bin に渡すオプション（設定ファイルのみ）（未実装） |
| `render.customServer.command` | string | (なし) | `STDG_RENDER_CUSTOM_SERVER_COMMAND` | カスタムレンダリングサーバのコマンド。設定時は hugo-bin の代わりに使用（未実装：AsciiDoc対応時に実装予定） |
