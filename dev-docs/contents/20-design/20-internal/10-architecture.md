# Architecture

## レイヤ構成

- **エントリポイント（`cli`）**: 利用者との入出力。操作そのものは持たない
- **command**: 一コマンドが一関数。結果を値で返し、端末への表示はエントリポイントに任せる
- **pipeline**: コンポーネントをステージに組み、build では一回、watch では入力が変わるたびに実行する。外部ツール（Hugo, watchdog）との接点もここ
- **components**: ビジネスロジック。入力ディレクトリから出力ディレクトリへの関数で、互いも pipeline も知らない
- **components/shared**: コンポーネント共通の基盤

## 起動時に受ける三つのもの

command は一回の実行の前に、性質の違う三つを別々に読む:

- **設定**（`config.py` の `ProjectConfig`）— 実行者が起動時に差し出すもの。どう実行しどこへ出すか（出力先、ポート等）と、テンプレートに届ける注入値 `vars`（`docs/reference/cli.md` の Injected values）。CLI 引数は CLI が解釈して渡し、環境変数は設定の側が直接読む
- **マニフェスト**（`components/manifest`）— プロジェクトが何か。`sbdb.yaml` を読み、世代と minimum version の検査を通す
- **配置**（`layout.py` の `SourceLayout`）— ソースの各パス。`project_dir` から導き、存在を検証する。世代ごとに配置が変わるなら、分岐はここに置く

三つは混ぜない。設定にソースの位置を動かす欄は無く、マニフェストにビルドの設定は無い。設定は `vars` を運ぶだけで、中身を読まない。利用者から見える理由は外部設計の [Manifest](../10-external/20-manifest.md#置き場と役割) と [CLI](../10-external/10-cli.md#置き場)。

設定は CLI が最初に組んで command に渡す。command はマニフェスト → 配置の順に読んでから、パイプラインを起こす。配置も契約面で、世代が違えば配置も違いうるので、配置の検査は世代の検査が通ったあとでしか意味を持たない。対応しない世代は「ソースが無い」より先に報告する（`command.py` の `build`）。

## build と watch を同じコンポーネントで賄う仕組み

コンポーネントは「このディレクトリを読んで、あのディレクトリに書く」関数で、一回限りか継続かを知らない。**ステージ**は、pipeline がそのコンポーネント一つに、監視する入力パス（利用者の入力ファイルと、直接の上流ステージの出力ディレクトリ）と出力ディレクトリを結び付けた実行単位。

build ではステージを依存順に一回ずつ走らせ、watch では各ステージが自分の監視パスの変更を待って再実行する:

```
利用者の入力 ─▶ Stage A ─▶ A/ ─▶ Stage B ─▶ B/ ─▶ ...
   (A が監視)            (B が監視)
```

watch では、上流が出力を書き換えれば下流が勝手に動くので、再実行の順序を中央で管理する必要がなく、変更は上流から下流へ伝わる。

これが成り立つには、各ステージの出力ディレクトリが原子的に更新され、途中状態が下流に見えないことが前提になる。この不変条件と、ステージ間を流れるデータの形（[JSON データモデル](30-communication/10-json-data-model.md)、[blob の運搬](30-communication/index.md#ステージ間の受け渡しは-hardlink)）は [Inter-Stage Communication](30-communication/index.md) に書く。

ステージがエラーで中断されることはない。コンポーネント内の処理で起きた例外は、コンポーネント共通の基盤（`Component` が関数を包む `error_propagation`）が出力の一部（`BuildReport`）に変換し、下流へ伝播させる。報告の運び方は [Inter-Stage Communication](30-communication/index.md#エラー伝播-buildreport)。

ステージの一覧と入出力は [Pipeline](20-pipeline.md) のステージ表が正本。

## コンポーネント構成

コンポーネントごとに、走らせるステージとコードの場所、担うことを示す。ステージの一覧は [Pipeline](20-pipeline.md)。

## SchemaInspector

`inspect_schema` — `components/preprocess/schema_inspector.py`

スキーマ定義を meta-schema で検証し、[データカタログ](30-communication/20-data-catalog.md)（スキーマから起こした entity と attribute の目録。後段のステージはスキーマの代わりにこれを読む）を抽出する。意図して保つ振る舞いは外部設計の [Schema](../10-external/30-schema.md)。

## Content Normalizer

`normalize_contents` — `components/preprocess/content_normalizer.py`

`contents/` の全ファイルを検証し、正規化して一つのデータ木に合流させ、x-ref と id を検査する。blob はレコードと別にバイト列を自分の出力へ写し、generate が各 edition の出力へ写し直す（[blob のアンカーパス](30-communication/index.md#blob-のアンカーパスは出力アドレスでもある)）。意図して保つ振る舞いは外部設計の [Schema](../10-external/30-schema.md)。

## Query Deriver

`derive_queries` — `components/preprocess/query_deriver.py`

views 入力を検証・正規化し、各ビュー定義をパースして派生 entity（`view: true`）をカタログから生成する。出力はカタログ全体: ビューをルートの属性に加えたデータカタログと、ビュー定義・派生 entity。意図して保つ振る舞いは外部設計の [View](../10-external/40-view.md)。

## Composer

`compose` — `components/composer/composer.py`

正規化済みデータとカタログをそのまま通し、ビュー定義を参照順に評価する。各ビューの結果は次のビューのソースにも加える。意図して保つ振る舞いは外部設計の [View](../10-external/40-view.md)。

## Tap

`tap` — `components/tap/tap.py`

compose の出力を一本の JSON 文書に合流させる。**Tap Schema**（`tap_schema`。`components/tap/tap_schema.py`）は derive_queries のカタログから、その文書の JSON Schema を書き出す。意図して保つ振る舞いは外部設計の [CLI](../10-external/10-cli.md)。

## Document Generator

`generate` — `components/generator/generator.py`

compose の出力を inert な木に詰め替え、各ノードに住所（アンカーパス）と型のメタデータを付け（`generator/data_tree.py`）、edition ごとにテンプレートで Markdown のページに描く。表紙と `__db/` のメタドキュメントもここが描く。

意図して保つ振る舞いは外部設計の [Template](../10-external/50-template.md)、[Reports](../10-external/60-reports.md)、[Trust Model](../10-external/70-trust-model.md)。

## Reconcile

`reconcile` — `components/generator/generator.py`

Generator の出力と、上流から伝播してきた `BuildReport` を突き合わせ、利用者に見せる最終出力を確定する。

エラー無しなら Generator の出力に奥付ページ（`__build_info/`）と警告ページ（`__warnings/`）を足し、表紙の末尾にリンク節を添える。エラーありなら出力を捨て、失敗ページを `index.md` に描く。意図して保つ振る舞いは外部設計の [Reports](../10-external/60-reports.md#表紙と診断ページ)。

Generator から分けるのは、Generator にエラー時の差し替えを持たせず、下流の site / publish に正常時と失敗時を区別させないため。

## Site Builder

`site`

生成された Markdown を HTML にレンダリングする。
