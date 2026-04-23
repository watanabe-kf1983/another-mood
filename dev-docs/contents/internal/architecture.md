# Architecture

## アーキテクチャ概要

5コンポーネント + レンダラー構成:

**SchemaInspector**
スキーマ定義を解析し、データカタログ（フィールド一覧）を抽出する。
IN: `schema_dir`
OUT: `inspect_schema_dir`

**Normalizer**
入力ディレクトリを検証し、辞書形式を配列形式に正規化する。
contents / queries の2種類の入力に対してそれぞれ独立したステージとして実行される。
Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する（[markdown-parser-spec.md](../design/normalizer/markdown-parser-spec.md) 参照）。
contents の Normalize では `--strict` モードで参照整合性もチェックする。
IN: `contents_dir`、`queries_dir`（各ステージで異なる。詳細は [pipeline.md](pipeline/pipeline.md) 参照）
OUT: `normalize_contents_dir`、`normalize_queries_dir`

**Composer**
正規化済みデータを自動的にビューとしてパススルーし、さらに正規化済みクエリがあれば評価して追加のビューを生成する。
IN: `inspect_schema_dir`、`normalize_contents_dir`、`normalize_queries_dir`
OUT: `compose_dir`

**Document Generator**
ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。
IN: `compose_dir`、`templates_dir`、`profilesFile`
OUT: `generate_dir`

**Reconcile**
Generator の出力と上流から伝播してきた `BuildReport` を突き合わせ、ユーザに見せる最終出力を確定する。エラー無しなら pass-through、エラーありなら `__build_failure` ページに差し替える。詳細は [components/generator.md](components/generator.md) 参照。
IN: `generate_dir`
OUT: `reconcile_dir`

**Document Renderer**
生成された Markdown を HTML にレンダリングする。
IN: `reconcile_dir`
OUT: `render_dir`

各コンポーネントはファイル監視のトリガーが異なるため、別プロセスとして動作する。入力データを変更すると normalized → views → documents とカスケードで更新される。

パイプライン構成:
- [pipeline/pipeline.md](pipeline/pipeline.md) — パイプライン構成

コンポーネント間通信:
- [json-data-model.md](json-data-model.md) — JSON データモデル（定義・マージ戦略・予約プレフィックス）

各コンポーネントの処理フローと技術選定:
- [components/schema-inspector.md](components/schema-inspector.md)
- [components/normalizer.md](components/normalizer.md)
- [components/composer.md](components/composer.md)
- [components/generator.md](components/generator.md)
- [components/renderer.md](components/renderer.md)

## ユーザプロジェクト構成

[project-structure.md](../design/app/project-structure.md) を参照。

## 設計判断

1. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
2. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
3. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
4. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
5. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う
6. **コンポーネント間はファイルを介して連携** - 各段階の結果を YAML ファイルとして目視確認でき、コンポーネントが疎結合になり、`rm -rf .another-mood/` でクリーンビルドできる

