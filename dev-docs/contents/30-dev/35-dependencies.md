# 依存関係の運用

依存ライブラリの版をどう宣言し、いつ・どう更新するかの規約。

## 制約の原則

- `pyproject.toml` の依存宣言は下限のみ（`>=`）。上限（cap）は原則書かない
- cap は「壊すリリースの実在が判明したとき」の応急処置に限る。**cap には除去条件（対応する移行タスク）を必ず併記する**

背景: mood は `uv tool install` で隔離 venv に入る配布ツールで、ユーザは uv.lock を受け取らず常に最新を解決する。上限なしのとき、依存の脆弱性修正はリリースの瞬間からユーザへ自動で流れる（自己治癒）。cap はこの自己治癒を堰き止めるので、恒久 cap は置かない。

## 三つの装置

| 装置 | 見るもの | 契機 | 守るもの | 応答 |
|---|---|---|---|---|
| Fresh dependency check | pyproject を最新版で解釈した環境 | 週次 | ユーザ（新規インストールが受け取る解決の代理） | cap（除去条件付き）or 修正 |
| Dependabot security updates（version updates は使わない——後述） | uv.lock + pyproject | CVE 公表時 | 開発環境・CI（lock で動く唯一の場所） | bump PR を即 merge |
| `make upgrade-deps` | uv.lock の鮮度 | タスク開始時 | 開発環境の陳腐化・lock 差分の小口化 | lock 単独 PR |

- Fresh dependency check は悪意あるリリースを踏む役（カナリア）を意図的に引き受ける。実行環境は使い捨て VM で、Actions キャッシュへの書き込みも遮断済み（fresh-deps.yml の `enable-cache: false`）——被害面は限定されている
- `make upgrade-deps` を省いても正しさは損なわれない（正しさは Fresh dependency check が週次で担保する）。儀式の価値は警報の pull 化（通知が届くのを待たず、開発を始めるたびに自分で測り直す）と差分の小口化にある

## タスク開始の儀式

`make upgrade-deps` は uv.lock を制約が許す最新へ振り直す。作業ツリーがクリーンならどのブランチからでも実行でき、解決は `origin/main` を土台に行って元いたブランチへ戻す。

- diff なし → そのままタスクに着手する
- diff あり → スクリプトが `deps/lock-refresh-<date>` ブランチで lock 単独 PR を作る。CI 緑を確認して `gh pr merge <branch> --squash --delete-branch` で merge してから着手する。赤なら修正 or 除去条件付き cap で対応する
- **lock 更新は機能 PR に同乗させない**。リグレッションの原因が機能変更か依存 bump かを分離できる形を保つ
- タスク途中で特定の版が要るときは `uv lock --upgrade-package <name>` を直接使ってよい

## 採らなかった選択肢

依存への一律 cap、定期 bot による lock 更新 PR、PR ごとの fresh 解決 CI、lock 単独 PR の auto-merge、冷却期間（dependency cooldown）を採らなかった理由は[背景](../90-appendix/30-dev/35-dependencies.md#採らなかった選択肢)。
