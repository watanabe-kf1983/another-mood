# Architecture

## Internal Design

### レイヤ構成

- **エントリポイント（`cli` / `mcp_server`）**: 利用者との入出力。操作そのものは持たない
- **command**: 一コマンドが一関数。結果を値で返し、CLI と MCP が同じ振る舞いになることを保証する
- **pipeline**: コンポーネントをステージに組み、build では一回、watch では入力が変わるたびに実行する。外部ツール（Hugo, watchdog）との接点もここ
- **components**: ビジネスロジック。入力ディレクトリから出力ディレクトリへの関数で、互いも pipeline も知らない（ファイル経由にした[経緯](../90-appendix/20-design/10-architecture.md#ステージ間の受け渡しをファイル経由にした経緯)）
- **components/shared**: コンポーネント共通の基盤

### build と watch を同じコンポーネントで賄う仕組み

コンポーネントは「このディレクトリを読んで、あのディレクトリに書く」関数で、一回限りか継続かを知らない。**ステージ**は、pipeline がそのコンポーネント一つに、入力として監視するパス（利用者の入力ファイルと、直接の上流ステージの出力ディレクトリ）と、書き先となる出力ディレクトリを結び付けた実行単位。build ではステージを依存順に一回ずつ走らせ、watch では各ステージが自分の監視パスの変更を待って再実行する:

```
利用者の入力 ─▶ Stage A ─▶ A/ ─▶ Stage B ─▶ B/ ─▶ ...
   (A が監視)            (B が監視)
```

watch では、上流が出力を書き換えれば下流が勝手に動くので、再実行の順序を中央で管理する必要がなく、変更は上流から下流へ伝わる。

これが成り立つには、各ステージの出力ディレクトリが原子的に更新され、途中状態が下流に見えないことが前提になる。この不変条件と、ステージ間を流れるデータの形（[JSON データモデル](40-communication/10-json-data-model.md)、[blob の運搬](40-communication/index.md#ステージ間の受け渡しは-hardlink)）は [Inter-Stage Communication](40-communication/index.md) に書く。

ステージがエラーで中断されることはない。コンポーネント内の処理で起きた例外は、コンポーネント共通の基盤（`Component` が関数を包む `error_propagation`）が出力の一部（`BuildReport`）に変換し、下流へ伝播させる。報告の運び方は [Inter-Stage Communication](40-communication/index.md#エラー伝播-buildreport)。

ステージの一覧と入出力は [pipeline.md](30-pipeline.md) のステージ表が正本。

### コンポーネント構成

以下のコンポーネント構成:

**SchemaInspector**
スキーマ定義を解析し、データカタログ（フィールド一覧）を抽出する。

**Content Normalizer**（[normalizer.md](50-normalizer/10-normalizer.md)）
contents 入力を検証し、辞書形式を配列形式に正規化する。
Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する（[markdown-parser-spec.md](50-normalizer/30-markdown-parser-spec.md) 参照）。
参照整合性もチェックする。

**Query Deriver**
views 入力を検証・正規化し、各ビュー定義をパースして派生エンティティ（`view: true`）をデータカタログから生成する。
出力には `__definition.views` と `__definition.entities` の両方を書き出す。

**Composer**
正規化済みデータを自動的にビューとしてパススルーし、さらにビュー定義があれば contents に対して適用して結果を出力する。派生エンティティは Query Deriver で生成済みのため Composer は views の passthrough として伝搬させる。

**Document Generator**（[generator.md](70-generator/10-generator.md)）
ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。

**Reconcile**
Generator の出力と上流から伝播してきた `BuildReport` を突き合わせ、ユーザに見せる最終出力を確定する。エラー無しなら pass-through、エラーありならビルド失敗ページに差し替える。詳細は [generator.md](70-generator/10-generator.md) 参照。

**Site Builder**
生成された Markdown を HTML にレンダリングする。

