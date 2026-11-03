# Inter-Stage Communication

ステージ間の受け渡し（[Architecture](../10-architecture.md#build-と-watch-を同じコンポーネントで賄う仕組み)）の総論。出力ディレクトリをどう下流へ運ぶか（運搬機構）、失敗をどう下流へ伝えるか（エラー伝播）、ファイルを介さず引数で渡すもの（build info）を扱う。流れるデータの形は [JSON データモデル](10-json-data-model.md)、スキーマから起こして全ステージが共有する目録は[データカタログ](20-data-catalog.md)。

## 運搬機構

workspace は、一回の実行でステージの出力ディレクトリが並ぶ作業ディレクトリ（利用者設定では `tmp_dir`、コードでは `Workspace.root`）。[ステージ構成](../20-pipeline.md#ステージ構成) の Output がその中身。

## ステージ間の受け渡しは hardlink

ステージ間・ステージ内の受け渡しは、ファイルをコピーせず **hardlink** で運ぶ。受け渡しはディレクトリの写しで行うので、コピーで運ぶと一つのファイルが hop の数だけ複製されるため。実バイトのコピーは contents → workspace の境界の 1 回だけになり、以降の hop はすべて同じ inode を共有する。

hardlink が張れない場合（別 FS をまたぐ、exFAT の外付けや SMB 共有など非対応の FS）はコピーに自動フォールバックし、[製品の動作環境](../../../10-concept/10-product.md#what) (Linux / macOS / Windows) を崩さない（`transfer.link_or_copy`）。

## ゆえに各ステージは write-once

hardlink は inode を共有するので、どこかのステージが既存ファイルに in-place で書き込むと、同じ inode を持つ全ディレクトリ（公開済み出力を含む）を突き破って書き換わり、しかもそこに watcher の event は飛ばない。

そこで **各ステージに write-once を課す**: workspace 内の既存ファイルに書き込んではならず、置換は必ず unlink → 再作成で行う。この制約が hardlink 運搬を安全にする。

ステージを構成するコンポーネントもアダプタ（Hugo 準備等）もこの制約の下にあり、実際のパイプラインを二周させて全ステージを検査する（`tests/pipeline/test_write_once_sweep.py`）。

利用者のソース（contents）はこの制約の外にあるので、境界では hardlink せず実コピーする。blob はこの境界コピーも、前回出力と size + mtime が一致すればそこからの hardlink で済ませる（`content_normalizer.py` の `_mirror_blob_bytes` / `_reuse_unchanged`）。

## 範囲と成立条件

- blob 限定でなく **全ファイル** を hardlink 対象にする。blob 判定述語をツリーの根ごとに持つと誤判定が即 inode 共有事故になるため、「全ファイル write-once」の一枚岩へ単純化した。
- `os.link` が成立するように、各ステージの temp を出力と同一 FS に置く（`dir_lock` の `mkdtemp`）。

## blob のアンカーパスは出力アドレスでもある

blob ノードのアンカーパス `/blob/<id>` を、各 edition の出力ルート直下に出力パスとして写す（住所からファイル名への変換は [Reports](../../10-external/60-reports.md)）。リンク解決（href が指す先）と blob の配置はどちらも `generate` が行い、`publish`（[ステージ表](../20-pipeline.md#ステージ構成)）は reconcile/ をそのまま写すだけなので、一つの住所で一致し、ずれない。

## 出力ディレクトリの更新は原子的

ディレクトリ単位では、各ステージの出力ディレクトリの更新は原子的で、途中状態は下流に見えない（[Architecture](../10-architecture.md#build-と-watch-を同じコンポーネントで賄う仕組み) が前提にする不変条件）。実装は `dir_lock` の `exclusive_write`（temp に書いて lock 下で出力へ同期）と `exclusive_read`（lock 下で上流の時点コピーを取る）。

実装と根拠の詳細は `transfer.py` / `dir_lock.py` の module docstring。

## エラー伝播: BuildReport

コンポーネント共通の基盤が例外から作る `BuildReport`（[Architecture](../10-architecture.md#build-と-watch-を同じコンポーネントで賄う仕組み)）は、各ステージの出力ディレクトリの `reports/` に置かれ、成果物の `data/` と並ぶ。下流は上流の `reports/` を集めてから本体を走らせ、失敗があれば本体を飛ばして報告だけを自分の `reports/` へ引き継ぐ。

## build info はデータの流れの外を通る

一回の実行の事実（処理系・注入値・マニフェスト）は `Workspace` の `build_info` が組む（`pipeline/workspace.py`。入れ子の値をドット区切りのキーに平坦化するのは `components/shared/build_info.py`）。

`generate`（テンプレートの `build_info` 関数）と `reconcile`（奥付ページと失敗ページ）には引数で渡し、`compose` の出力には入らない。

失敗したステージは成果物を出さず `BuildReport` だけを下流へ渡すので、build info をデータとして preprocess から流すと、上流で失敗したとき `reconcile` には届かず、失敗ページに奥付を出せない。利用者から見える理由（ビューの出力をマシンに依存させない）は [Template](../../10-external/50-template.md#build-info-はテンプレートだけが読みデータ層には流さない)。
