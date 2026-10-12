# 出力の構成

生成器が書き出す出力ツリーの設計。edition と、ページ・マウントの置き場所を扱う。`__db/` と `__build_info/` の中身は [メタドキュメンテーション](../75-meta-documentation/index.md)。

## External Design

### edition

**edition** は、同じ report の体裁違いの出力。どの edition も同じデータを同じテンプレートで描き、違うのは `file_per`（どの型のノードを別ファイルに分けるか、という分割粒度）だけ。たとえば web 向けにはページを細かく分け、印刷向けには 1 ファイルにまとめる、という使い分けを想定している。宣言された edition はすべて 1 回のビルドで生成され、`{outDir}/{edition}/` に横並びに公開される。

edition は、環境ごとに 1 つを選んで切り替える profile **ではない**。ビルド時に 1 つを選ぶ `--edition` のようなオプションも持たない。レンダラやフォーマットの違いを表す軸でもない（Markdown→HTML の変換は全 edition で同一）。「並列出力」と言うとき、それは成果物が並ぶ意味であって concurrency の意味ではない。

DB 自己記述の `__db/` は edition の機構で描くが、体裁違いの report ではないので、表紙では Reports に並べず別エントリに置く。

edition は `definition/reports.yaml` に宣言する。`editions:` マップに名前付きで複数書くか、マップを省いてトップレベルに `file_per` を書く。後者は `default` という名の唯一の edition を宣言したものと見なされる。構文は `docs/reference/reports.md`、edition 名の規則と両形式の排他検証は `resources/schemas/reports-schema.yaml` が正本。

### ページパスと出力ディレクトリ

ページパスは `PagingPolicy.page_path` が anchor_path から導く（[anchor-spec.md](30-anchor-spec.md#ページパスの導出)）。`page_path` は **edition ルート相対**で、実ファイルは render が edition のマウント先を被せた `{outDir}/{edition}/{page_path}` に書き出す（form A は暗黙 edition `default`）。root の入口には薄い**表紙**（cover。edition ではなく一回 render）を置き、システム生成のメタ（DB の自己記述）は `__db/` マウントへ退避する:

```
{outDir}/
  index.md                                     ← 表紙（cover。H1=project 名 / Reports + Database Information）
  default/   (form B なら web/ print/)          ← ユーザ edition（report 本体）
  __db/                                        ← DB 自己記述（メタ edition のマウント先）
    index.md                                     メタ index（ER 図・entity/view 一覧）
    __data/  __entity_defs/  __view_defs/        診断（edition 横断・常に __db 内の同位置）
  __build_info/  __warnings/                   ← build-report 層（reconcile が置き、表紙末尾にリンクを append）
```

`__db/` の内側は [DB 自己記述](../75-meta-documentation/10-database-information.md)、`__build_info/` は [奥付](../75-meta-documentation/20-build-information.md)、`__warnings/` と失敗ページは [ビルドレポート](../75-meta-documentation/30-build-report.md)。

マウントはリンク解決に**透過**: リンク URL は page 相対（`node_href`）なので `{edition}/` や `__db/` のマウント接頭辞は効かず、各 edition / マウントは自己完結した相対リンクのサブツリーになる（[anchor-spec.md のリンク解決](30-anchor-spec.md#リンク解決)）。

## Proposals

### Edition 別ルートテンプレート（将来）

edition ごとに異なるルートテンプレート（`index.md` 以外）を**利用者が `reports.yaml` で指定したい**需要（Web 版と印刷版でトップ構成を変える等）。**機構（`Edition` の `root_template` / `templates_dir` フィールドと `generate()` ループでの差し替え）は既にある**ので、残るは reports.yaml への設定露出（`root_template` エントリのパースと `load_editions` での反映）のみ。加算的拡張。
