# Architecture

## アーキテクチャ概要

3コンポーネント + レンダラー構成:

**Normalizer**
スキーマ定義に基づいてデータを検証し、辞書形式を配列形式に正規化する。
Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する（[markdown-parser-spec.md](../external/normalizer/markdown-parser-spec.md) 参照）。
`--strict` モードでは参照整合性もチェックする。
IN: `schemaDir`、`contentsDir`
OUT: `normalizedDir`

**Composer**
正規化済みデータを自動的にビューとしてパススルーし、さらに YAML DSL のクエリがあれば評価して追加のビューを生成する。
IN: `normalizedDir`、`queriesDir`（任意）
OUT: `viewsDir`

**Document Generator**
ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。
IN: `viewsDir`、`templatesDir`、`profilesFile`
OUT: `outDir`

**Document Renderer**
生成された Markdown を HTML にレンダリングする。
IN: `outDir`
OUT: `render.outDir`

各コンポーネントはファイル監視のトリガーが異なるため、別プロセスとして動作する。data/ を変更すると normalized/ → views/ → documents/ とカスケードで更新される。

パイプライン構成とプロセス連携:
- [pipeline/pipeline.md](pipeline/pipeline.md) — パイプライン構成
- [pipeline/process-coordination.md](pipeline/process-coordination.md) — プロセス間連携
- [pipeline/stage-runner.md](pipeline/stage-runner.md) — StageRunner（出力の原子性・順序性）

各コンポーネントの処理フローと技術選定:
- [components/normalizer.md](components/normalizer.md)
- [components/composer.md](components/composer.md)
- [components/generator.md](components/generator.md)
- [components/renderer.md](components/renderer.md)

## ユーザプロジェクト構成

[project-structure.md](../external/app/project-structure.md) を参照。

## 設計判断

1. **既存ツールを最大限活用** - 車輪の再発明を避ける
2. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
3. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
4. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
5. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
6. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う

