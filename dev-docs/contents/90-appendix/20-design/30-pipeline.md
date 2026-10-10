# Pipeline (appendix)

[Pipeline](../../20-design/30-pipeline.md) の背景。

## Watch ライブラリは watchdog を採用

[watchdog](https://github.com/gorakhargosh/watchdog) を採用。過去に [watchfiles](https://github.com/samuelcolvin/watchfiles) を採用していた (PR #41) が、watchfiles は WSL を検出すると WSL1/WSL2 を区別せず強制 polling に切り替える挙動があり (issue #187、2022)、WSL2 環境で polling モードの event 取りこぼしが発生して watch が停止する問題があった (実測で `mood watch` 稼働中に concurrent `mood build` を当てると 10 回中 7 回最終状態が "failed" で固定)。

watchdog は Linux (WSL2 を含む) で inotify を使い、明示的に指定しない限り polling に落ちないため、WSL1 のような特殊ケースを考慮しなくてよい。OS ネイティブの event 通知機構を使う点は両ライブラリ共通だが、WSL の自動 polling 判定の挙動が異なる。

もう一点の差は読み取り系 event の扱い。inotify は `IN_OPEN / IN_CLOSE_NOWRITE` などの読み取り系 event も emit し、watchfiles は library レベルでこれを filter するが、watchdog のデフォルト (`on_any_event`) は拾ってしまう。watchdog 側で変更系 event のみに subscribe する申し送りは `pipeline/adapters/watcher.py` の `_Handler` コメントにある。
