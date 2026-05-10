# Architecture

## アーキテクチャ概要

以下のコンポーネント構成:

**SchemaInspector**
スキーマ定義を解析し、データカタログ（フィールド一覧）を抽出する。
IN: `schema_file`
OUT: `inspect_schemas_dir`

**Content Normalizer**
contents 入力を検証し、辞書形式を配列形式に正規化する。
Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する（[markdown-parser-spec.md](normalizer/markdown-parser-spec.md) 参照）。
`--strict` モードで参照整合性もチェックする。
IN: `contents_dir`、`inspect_schemas_dir`
OUT: `normalize_contents_dir`

**Query Deriver**
queries 入力を検証・正規化し、各クエリをパースして派生エンティティ（`view: true`）をデータカタログから生成する。
出力 YAML には `__definition.queries` と `__definition.entities` の両方を書き出す。
IN: `queries_dir`、`inspect_schemas_dir`
OUT: `derive_queries_dir`

**Composer**
正規化済みデータを自動的にビューとしてパススルーし、さらにクエリ定義があれば contents に対して適用して結果を出力する。派生エンティティは Query Deriver で生成済みのため Composer は queries の passthrough として伝搬させる。
IN: `inspect_schemas_dir`、`normalize_contents_dir`、`derive_queries_dir`
OUT: `compose_dir`

**Document Generator**
ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。
IN: `compose_dir`、`templates_dir`、`profilesFile`
OUT: `generate_dir`

**Reconcile**
Generator の出力と上流から伝播してきた `BuildReport` を突き合わせ、ユーザに見せる最終出力を確定する。エラー無しなら pass-through、エラーありなら `__build_failure` ページに差し替える。詳細は [generator.md](generator/generator.md) 参照。
IN: `generate_dir`
OUT: `reconcile_dir`

**Document Renderer**
生成された Markdown を HTML にレンダリングする。
IN: `reconcile_dir`
OUT: `render_dir`

各コンポーネントはファイル監視のトリガーが異なるため、別プロセスとして動作する。入力データを変更すると normalized → views → documents とカスケードで更新される。

パイプライン構成:
- [pipeline.md](pipeline.md) — パイプライン構成

コンポーネント間通信:
- [json-data-model.md](json-data-model.md) — JSON データモデル（定義・マージ戦略・予約プレフィックス）

各コンポーネントの処理フローと技術選定:
- [normalizer.md](normalizer/normalizer.md)
- [generator.md](generator/generator.md)

## ユーザプロジェクト構成

[project-structure.md](app/project-structure.md) を参照。

## 設計判断

1. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
2. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
3. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
4. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
5. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う
6. **コンポーネント間はファイルを介して連携** - 各段階の結果を YAML ファイルとして目視確認でき、コンポーネントが疎結合になり、`rm -rf .another-mood/` でクリーンビルドできる

## 動作環境

Linux / macOS / Windows のいずれでも動作する cross-platform を維持する。Windows 利用者も主要ターゲットに含む。

## proposal

### Windows POSIX 依存の修正 (O3)

判明している runtime の POSIX 依存: `src/another_mood/pipeline/render.py` の `_NORMAL_EXIT_CODES` で signal 値の負値（`-SIGTERM` / `-SIGINT`）をマッチしている箇所。Windows の `TerminateProcess` は負の signal 値で exit しないため、Windows 環境では「正常終了」が「異常終了」とログされる。Phase 10 タスク [O3](../../tasks.md)。

