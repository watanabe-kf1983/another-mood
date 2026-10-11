# 出力の構成

生成器が書き出す出力ツリーの設計。edition と、ページ・マウントの置き場所を扱う。`__db/` と `__build_info/` の中身は [メタドキュメンテーション](../75-meta-documentation/index.md)。

## External Design

### edition

**edition** は、同じ report の体裁違いの出力。どの edition も同じデータを同じテンプレートで描き、違うのは `file_per`（どの型のノードを別ファイルに分けるか、という分割粒度）だけ。たとえば web 向けにはページを細かく分け、印刷向けには 1 ファイルにまとめる、という使い分けを想定している。宣言された edition はすべて 1 回のビルドで生成され、`{outDir}/{edition}/` に横並びに公開される。

edition は、環境ごとに 1 つを選んで切り替える profile **ではない**。ビルド時に 1 つを選ぶ `--edition` のようなオプションも持たない。レンダラやフォーマットの違いを表す軸でもない（Markdown→HTML の変換は全 edition で同一）。「並列出力」と言うとき、それは成果物が並ぶ意味であって concurrency の意味ではない。

edition は `definition/reports.yaml` に宣言する。`editions:` マップに名前付きで複数書くか、マップを省いてトップレベルに `file_per` を書く。後者は `default` という名の唯一の edition を宣言したものと見なされる。構文は `docs/reference/reports.md`、edition 名の規則と両形式の排他検証は `resources/schemas/reports-schema.yaml` が正本。

### ページパスと出力ディレクトリ

> **[W4 dup]** 導出規則 ↔ edition.py:71-95 (a)、10-generator:31-35 (c)、template.md:118-122、reports.md:45-47 (b) — 完全。出力図 ↔ guides.md:70-81 (部分)。__db/__entity_defs ↔ edition.py:136-139、10-json-data-model 予約プレフィックス (部分)。build-report 層 ↔ generator.py、10-generator:66-68 (部分)。案: 導出規則の再述は削除 (generator.md へポインタ)。出力図と「2 種で捉える」は残す

ページパスの導出規則（anchor_path 由来、root は `index.md`、セグメントは anchor_path と同じ IRI エスケープを継承）は `PagingPolicy.page_path` が持ち、正本は [anchor-spec.md](30-anchor-spec.md#ページパスの導出)。`page_path` は **edition ルート相対**で、実ファイルは render が edition のマウント先を被せた `{outDir}/{edition}/{page_path}` に書き出す（form A は暗黙 edition `default`）。root の入口には薄い**表紙**（cover。edition ではなく一回 render）を置き、システム生成のメタ（DB の自己記述）は `__db/` マウントへ退避する:

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

## Internal Design

### 表紙の edition 列挙

> **[W4 dup]** ↔ resources/templates/cover/index.md:1-13、stages.py:130-131、meta/index.md:3 (a, 完全)。機構。案: 削除→コード。「__db/ を直書きしない」「project 名依存を 1 箇所に」はテンプレートのコメントへ

表紙はデータループと**同じ `editions` 集合**を受け取り、`Edition.is_system` で 2 セクションへ振り分ける。決定:

- **H1 は project 名**（manifest の `title`、無ければ `project_dir` の basename）。
- `## Reports` = 非 system（ユーザ edition）を列挙、`## Database Information` = system（メタ edition）へ 1 本リンク。
- `## Database Information` のリンク先は**メタ edition の `dir_segment` から導出**（`__db/` を直書きしない）ので、マウント名を変えても追従する。
- 着地する `__db/index.md` の H1 は固定 `# Database Information` — 表紙の同名セクションから同名ページへ着く導線を保ち、project 名依存を表紙 1 箇所に閉じ込める。

## Proposals

### Edition 別ルートテンプレート（将来）

edition ごとに異なるルートテンプレート（`index.md` 以外）を**利用者が `reports.yaml` で指定したい**需要（Web 版と印刷版でトップ構成を変える等）。**機構（`Edition` の `root_template` / `templates_dir` フィールドと `generate()` ループでの差し替え）は既にある**ので、残るは reports.yaml への設定露出（`root_template` エントリのパースと `load_editions` での反映）のみ。加算的拡張。
