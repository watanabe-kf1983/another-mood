# Component Communication

コンポーネントはパイプライン各段の結果をファイルとして受け渡すことで連携する（[architecture](../10-architecture.md#設計判断) 設計判断 #6 の精緻化）。ファイル経由ゆえに各段を YAML として目視確認でき、コンポーネントが疎結合になり、`rm -rf .another-mood/` でクリーンビルドできる。本章は通信の**総論** — ファイルをどう運ぶか（運搬機構）と、失敗をどう伝えるか（エラー伝播）— を扱う。通信されるデータクラスの**各論**は [JSON データモデル](10-json-data-model.md) / [prose](20-prose-spec.md) / [blob](30-blob-spec.md)。

## Internal Design

### 運搬機構: workspace の write-once 不変条件と hardlink

不変条件: **workspace 内の全ファイルは write-once** — 既存ファイルへの in-place 書き込みは禁止し、置換は必ず unlink → 再作成で行う。

この一枚岩の不変条件が、workspace 内のファイル受け渡しを **hardlink** で行うことを安全にする。ステージ間・ステージ内の hop はコピーせず hardlink で運び（`transfer.link_or_copy`: dst があれば unlink → `os.link` → 別 FS・非対応 FS では `copy2` フォールバック）、実バイトコピーは contents → workspace の境界 1 回に絞れる。in-place 書き込みを許すと、inode を共有する全ディレクトリ（公開済み出力を含む）を突き破って書き換えてしまい、かつそこに watcher の event も飛ばないため、write-once が hardlink 運搬の前提になる。

- blob 限定でなく **全ファイル** を hardlink 対象にする。blob 判定述語をツリーの根ごとに持つと誤判定が即 inode 共有事故になるため、「全ファイル write-once」の一枚岩へ単純化した。`link_or_copy` の「dst があれば unlink」がこの不変条件の中央実装。
- `os.link` の成立条件として、各ステージの temp を出力と同一 FS に置く（`dir_lock` の `mkdtemp`）。
- cross-platform: hardlink が張れない環境（別 FS・Windows・非対応 FS）では `copy2` に自動フォールバックするので、[動作環境](../10-architecture.md#動作環境) の cross-platform 要件を崩さない。

実装と根拠の詳細は `transfer.py` / `dir_lock.py` の module docstring。データクラス別の運搬（blob の境界コピー・前回出力からの増分再利用）は [blob](30-blob-spec.md) の各論。

### エラー伝播: BuildReport

各ステージのエラーは即座に停止させず、`BuildReport` として upstream から下流へ伝播させる。最終出力は **reconcile** ステージが「Generator の出力（あるべき姿）」と「伝播してきた BuildReport（実際に起きたこと）」を突き合わせて確定する — エラー無しは pass-through、エラー有りは `__build_failure` ページへ差し替え。これにより下流（Render / publish）は reconcile 出力の単一視点だけを持てばよく、正常時・エラー時の分岐を知らずに済む。ステージ挙動の詳細は [generator.md の Reconcile 節](../70-generator/10-generator.md#reconcile)。
