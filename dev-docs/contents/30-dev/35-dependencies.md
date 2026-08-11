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
| Dependabot security updates | uv.lock + pyproject | CVE 公表時 | 開発環境・CI（lock で動く唯一の場所） | bump PR を即 merge |
| `make upgrade-deps` | uv.lock の鮮度 | タスク開始時 | 開発環境の陳腐化・lock 差分の小口化 | lock 単独 PR |

- Fresh dependency check は悪意あるリリースを踏む役（カナリア）を意図的に引き受ける。実行環境は使い捨て VM + read-only トークンで、Actions キャッシュへの書き込みも遮断済み（fresh-deps.yml の `enable-cache: false`）——被害面は限定されている
- `make upgrade-deps` は義務ではなく原則。正しさは Fresh dependency check が週次で担保しており、儀式の価値は警報の pull 化（通知が届くのを待たず、開発を始めるたびに自分で測り直す）と差分の小口化にある

## タスク開始の儀式

`make upgrade-deps` は uv.lock を制約が許す最新へ振り直す。

- diff なし → そのままタスクに着手する
- diff あり → スクリプトが `deps/lock-refresh-<date>` ブランチで lock 単独 PR を作る。CI 緑を確認して `gh pr merge <branch> --squash --delete-branch` で merge してから着手する。赤なら修正 or 除去条件付き cap で対応する
- **lock 更新は機能 PR に同乗させない**。リグレッションの原因が機能変更か依存 bump かを分離できる形を保つ
- タスク途中で特定の版が要るときは `uv lock --upgrade-package <name>` を直接使ってよい

## 採らなかった選択肢

- **依存への一律 cap**: 上限は未来のリリースへの推測で、動くメジャーを弾き壊すマイナーを通す。ユーザ側の脆弱性修正の自己治癒も止まる
- **定期 bot による lock 更新 PR**（Dependabot version updates / Renovate lockFileMaintenance / 自前ワークフロー）: bot は放置問題を解決しない（merge する人間は依然必要）。さらに定期 bot は自分の commit で GitHub の 60 日 scheduled workflow 自動停止を自ら回避し続けるため、開発休止後も無人で main を変異させ、赤 PR を無限に積む。鮮度維持は開発活動に結合させ、開発が止まればシステム全体も静止する設計を採る。開発が長期休眠して儀式が回らなくなった場合の格上げ先は Renovate lockFileMaintenance
- **PR ごとの fresh 解決 CI**: upstream のリリースが無関係な PR をブロックする。週次への隔離（fresh-deps.yml の設計理由）を維持する
- **lock 単独 PR の auto-merge**: 必要承認数 0 のソロ構成では、auto-merge の解禁がそのまま無人 merge の解禁になる。merge は CI 緑を確認して手動一発で足りる
- **冷却期間（dependency cooldown）**: 公開から N 日未満の版を除外する供給網攻撃対策（<https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns>）。検討の上不採用。ただし理由は「当たる確率が低い」ではない——乗っ取りリリースは稀だが被害が不可逆な型で、頻度で割り引いてよい対象ではない。

    判断は層と道具で下す。冷却を uv.lock に置いても守れるのは開発環境だけで、ユーザには届かない（uv.lock を受け取らず、常に最新を解決する。制約の原則の背景を参照）。そして手元の `uv lock --exclude-newer` はそもそも冷却ではない——「公開から N 日待つ」滑走窓ではなく絶対日付のカットオフで、日付が uv.lock に刻印として残って後続の解決を汚染し、意図して入れた新しい版（Dependabot のセキュリティ修正、速達で入れた pin）まで「カットオフより若い」という理由で巻き戻す。

    得られる保護は近似で不確実（未知の悪意に当たるかどうか）、払う代償は確実（既知の脆弱性修正の到達を自分から遅らせる）。確率で測らないなら、判断軸はこの非対称のほうに置く。開発環境が悪意あるリリースに被曝しうる状態は残るが、これは受け入れた残余リスクであって、対策済みではない。

    再訪トリガー: uv がインストーラ層の既定冷却（pnpm の minimumReleaseAge 相当の滑走窓）を実装したら、それに乗る——層も道具も正しくなる
