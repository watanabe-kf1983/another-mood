# Architecture

## External Design

### ユーザプロジェクト構成

[project-structure.md](20-app/10-project-structure.md) を参照。

### 設計判断

> **[W4 dup]** ↔ #3: 20-app/10-project-structure MS-Access 節末尾 / #4: 30-mcp-design 基本方針 / #6: 40-communication/index.md 冒頭 (c, 完全)。原則の一覧。案: 残す (一覧は導線、理由は各ファイル側)

1. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
2. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
3. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
4. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
5. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う
6. **コンポーネント間はファイルを介して連携** - 各段階の結果をファイルとして目視確認でき、コンポーネントが疎結合になり、`rm -rf .another-mood/` でクリーンビルドできる

### 動作環境

Linux / macOS / Windows のいずれでも動作する cross-platform を維持する。Windows 利用者も主要ターゲットに含む。

## Internal Design

### アーキテクチャ概要

> **[W4 dup]** ↔ 10-background/10-product.md Key Concepts、stages.py 各 factory docstring (部分)。Reconcile 段落 ↔ 40-communication/index.md:21、70-generator/10-generator.md Reconcile 節 (c, 完全)。構造の概要。案: 残す (要約+ポインタの範囲)

以下のコンポーネント構成:

**SchemaInspector**
スキーマ定義を解析し、データカタログ（フィールド一覧）を抽出する。

**Content Normalizer**
contents 入力を検証し、辞書形式を配列形式に正規化する。
Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する（[markdown-parser-spec.md](50-normalizer/30-markdown-parser-spec.md) 参照）。
参照整合性もチェックする。

**Query Deriver**
views 入力を検証・正規化し、各ビュー定義をパースして派生エンティティ（`view: true`）をデータカタログから生成する。
出力には `__definition.views` と `__definition.entities` の両方を書き出す。

**Composer**
正規化済みデータを自動的にビューとしてパススルーし、さらにビュー定義があれば contents に対して適用して結果を出力する。派生エンティティは Query Deriver で生成済みのため Composer は views の passthrough として伝搬させる。

**Document Generator**
ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。

**Reconcile**
Generator の出力と上流から伝播してきた `BuildReport` を突き合わせ、ユーザに見せる最終出力を確定する。エラー無しなら pass-through、エラーありならビルド失敗ページに差し替える。詳細は [generator.md](70-generator/10-generator.md) 参照。

**Site Builder**
生成された Markdown を HTML にレンダリングする。

各コンポーネントの入出力ディレクトリと依存順序は [pipeline.md](30-pipeline.md) のステージ表が正本。各コンポーネントはファイル監視のトリガーが異なるためそれぞれ独立した watcher スレッドを持ち、入力データを変更すると上流から下流へカスケードで更新される。

パイプライン構成:
- [pipeline.md](30-pipeline.md) — パイプライン構成

コンポーネント間通信:
- [communication](40-communication/index.md) — 総論（運搬機構: workspace の write-once 不変条件・hardlink / エラー伝播: BuildReport）と、通信されるデータクラスの各論（[JSON データモデル](40-communication/10-json-data-model.md) / [prose](40-communication/20-prose-spec.md) / [blob](40-communication/30-blob-spec.md)）

各コンポーネントの処理フローと技術選定:
- [normalizer.md](50-normalizer/10-normalizer.md)
- [generator.md](70-generator/10-generator.md)

