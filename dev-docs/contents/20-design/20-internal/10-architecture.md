# Architecture

## Internal Design

### レイヤ構成

- **エントリポイント（`cli`）**: 利用者との入出力。操作そのものは持たない
- **command**: 一コマンドが一関数。結果を値で返し、端末への表示はエントリポイントに任せる
- **pipeline**: コンポーネントをステージに組み、build では一回、watch では入力が変わるたびに実行する。外部ツール（Hugo, watchdog）との接点もここ
- **components**: ビジネスロジック。入力ディレクトリから出力ディレクトリへの関数で、互いも pipeline も知らない
- **components/shared**: コンポーネント共通の基盤

### build と watch を同じコンポーネントで賄う仕組み

コンポーネントは「このディレクトリを読んで、あのディレクトリに書く」関数で、一回限りか継続かを知らない。**ステージ**は、pipeline がそのコンポーネント一つに、監視する入力パス（利用者の入力ファイルと、直接の上流ステージの出力ディレクトリ）と出力ディレクトリを結び付けた実行単位。

build ではステージを依存順に一回ずつ走らせ、watch では各ステージが自分の監視パスの変更を待って再実行する:

```
利用者の入力 ─▶ Stage A ─▶ A/ ─▶ Stage B ─▶ B/ ─▶ ...
   (A が監視)            (B が監視)
```

watch では、上流が出力を書き換えれば下流が勝手に動くので、再実行の順序を中央で管理する必要がなく、変更は上流から下流へ伝わる。

これが成り立つには、各ステージの出力ディレクトリが原子的に更新され、途中状態が下流に見えないことが前提になる。この不変条件と、ステージ間を流れるデータの形（[JSON データモデル](30-communication/10-json-data-model.md)、[blob の運搬](30-communication/index.md#ステージ間の受け渡しは-hardlink)）は [Inter-Stage Communication](30-communication/index.md) に書く。

ステージがエラーで中断されることはない。コンポーネント内の処理で起きた例外は、コンポーネント共通の基盤（`Component` が関数を包む `error_propagation`）が出力の一部（`BuildReport`）に変換し、下流へ伝播させる。報告の運び方は [Inter-Stage Communication](30-communication/index.md#エラー伝播-buildreport)。

ステージの一覧と入出力は [pipeline.md](20-pipeline.md) のステージ表が正本。

### コンポーネント構成

コンポーネントごとに、走らせるステージとコードの場所、担うことを示す。ステージの一覧は [pipeline.md](20-pipeline.md)。

#### SchemaInspector

`inspect_schema` — `components/preprocess/schema_inspector.py`

スキーマ定義を meta-schema で検証し、[データカタログ](30-communication/20-data-catalog.md)（スキーマから起こした entity と attribute の目録。後段のステージはスキーマの代わりにこれを読む）を抽出する。意図して保つ振る舞いは外部設計の [Schema](../10-external/30-schema.md)。

#### Content Normalizer

`normalize_contents` — `components/preprocess/content_normalizer.py`

`contents/` の全ファイルを検証し、正規化して一つのデータ木に合流させ、x-ref と id を検査する。blob はレコードと別にバイト列を出力へ写す（[運搬機構](30-communication/index.md#運搬機構)）。意図して保つ振る舞いは外部設計の [Schema](../10-external/30-schema.md)。

#### Query Deriver

`derive_queries` — `components/preprocess/query_deriver.py`

views 入力を検証・正規化し、各ビュー定義をパースして派生エンティティ（`view: true`）をカタログから生成する。出力はカタログ全体: ビューをルートの属性に加えたデータカタログと、ビュー定義・派生エンティティ。意図して保つ振る舞いは外部設計の [View](../10-external/40-view.md)。

#### Composer

`compose` — `components/composer/composer.py`

正規化済みデータとカタログをそのまま通し、ビュー定義を参照順に評価する。各ビューの結果は次のビューのソースにも加える。意図して保つ振る舞いは外部設計の [View](../10-external/40-view.md)。

#### Tap

`tap` — `components/tap/tap.py`

compose の出力を一本の JSON 文書に合流させる。**Tap Schema**（`tap_schema`。`components/tap/tap_schema.py`）は derive_queries のカタログから、その文書の JSON Schema を書き出す。意図して保つ振る舞いは外部設計の [CLI](../10-external/10-cli.md)。

#### Document Generator

`generate` — [generator](../30-pending/70-generator/index.md)

ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。

#### Reconcile

`reconcile`

Generator の出力と上流から伝播してきた `BuildReport` を突き合わせ、ユーザに見せる最終出力を確定する。エラー無しなら pass-through、エラーありならビルド失敗ページに差し替える。詳細は [build-report.md](../30-pending/75-meta-documentation/30-build-report.md) 参照。

#### Site Builder

`site`

生成された Markdown を HTML にレンダリングする。

### ステージをまたぐ約束

地図を保つものではないが、複数のステージが共に守る不変条件。

**参照の検査は二層に分け、混ぜない。** entity 間の参照（x-ref）は `normalize_contents` が合流後の木で検査する（`data_fk_validator.py`）。文書間のリンク（`node:` 記法）は `generate` がリンク解決で検査する（`relink` フィルタ）。

`normalize_contents` は prose 本文の相対リンクをレキシカルに `node:` 化するだけで、リンク先の存在は見ない。

x-ref はクエリでの結合先を保証するデータの関心であり、リンクは出力世界の関心。だから見出しへのリンクを x-ref で縛ったり、見出しを entity に起こしたりはしない。

**ビューの形は、データを見ずに決まる。** クエリの各句は、レコード変換（`apply`）と[データカタログ](30-communication/20-data-catalog.md)の変換（`derive`）を同じ DSL 断片から対で持つ（`components/shared/query.py`）。

`derive_queries` は `derive` で、ビューの出力の形を派生 entity としてカタログに載せる。`compose` は同じ `Query` の `apply` でレコードを作る。

両者は同じ順で同じ句を通り、句ごとの対が整合しているので、compose の出力は derive_queries が宣言した形に一致する。下流（`generate` のメタドキュメント、`tap_schema`）はデータを見ずにカタログを信じてよい。句を足すときは両方を対で足す。

**blob のアンカーパスは出力アドレスでもある。** blob ノードのアンカーパス `/blob/<id>` を、各 edition の出力ルート直下にそのまま出力パスとして写す。`generate` のリンク解決（href が指す先）と `publish` の配置が一つの住所で一致し、ずれない。

ページパスはノードのアンカーパスから導かれ、`/blob/` の根は内蔵 entity `blob` の住所なので、利用者の entity やビューのページがそこに入ることはない。よってページパスとの衝突検査を持たない（`generator.py` の `_BLOB_NAMESPACE`、`pipeline/adapters/preparation.py` の `_is_blob`）。
