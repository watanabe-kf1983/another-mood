# 依存関係の運用 (appendix)

[依存関係の運用](../../30-dev/35-dependencies.md) の背景。

## 採らなかった選択肢

- **依存への一律 cap**: 上限は未来のリリースへの推測で、動くメジャーを弾き壊すマイナーを通す
- **定期 bot による lock 更新 PR**（Dependabot version updates / Renovate lockFileMaintenance / 自前ワークフロー）: bot は放置問題を解決しない（merge する人間は依然必要）。さらに定期 bot は自分の commit で GitHub の 60 日 scheduled workflow 自動停止を自ら回避し続けるため、開発休止後も無人で main を変異させ、赤 PR を無限に積む。鮮度維持は開発活動に結合させ、開発が止まればシステム全体も静止する設計を採る。開発が長期休眠して儀式が回らなくなった場合の格上げ先は Renovate lockFileMaintenance
- **PR ごとの fresh 解決 CI**: upstream のリリースが無関係な PR をブロックする。週次への隔離（fresh-deps.yml の設計理由）を維持する
- **lock 単独 PR の auto-merge**: 必要承認数 0 のソロ構成では、auto-merge の解禁がそのまま無人 merge の解禁になる。merge は CI 緑を確認して手動一発で足りる
- **冷却期間（dependency cooldown）**: 公開から N 日未満の版を除外する供給網攻撃対策（<https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns>）
    - 理由 1: `uv lock --exclude-newer` は日付が uv.lock に刻印として残り、後続の解決を汚染する
    - 理由 2: 速達で入れた版や Dependabot のセキュリティ修正を「カットオフより若い」という理由で必ず巻き戻す——機能している防御への確実な干渉
    - 理由 3: それで得られる遮蔽は部分的。乗っ取りリリースが開発環境で実行される失敗モード自体は閉じず、発現を数日ずらすだけで、休眠ペイロード型の適応には無力
    - 代わりの防御: 踏むリスクは受け入れ、踏んだことに気づく検知（Dependabot アラート・yank の尊重）と、踏んだときの被害を限る隔離（fresh 系ジョブのキャッシュ遮断、リリースの trusted publishing）に頼る
    - 再訪トリガー: uv がインストーラ層のデフォルト冷却（pnpm の minimumReleaseAge 相当）を実装したら、生態系標準の設計（セキュリティ更新のバイパス等）ごと乗る
