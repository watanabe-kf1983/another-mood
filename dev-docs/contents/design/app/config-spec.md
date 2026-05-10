# 設定システム仕様

## External Design

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](../../../tasks.md)）
3. 環境変数
4. CLI 引数

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

### render.customServer.command (G3)

> **未実装** — Phase 10 タスク [G3](../../../tasks.md)。

カスタムレンダリングサーバのコマンドを設定すると、Hugo の代わりに使用される。詳細は下表。

### 未実装の config キー

| キー | 型 | デフォルト | 環境変数 | CLI | タスク | 説明 |
|------|-----|---------|----------|-----|------|------|
| `profilesFile` | string | `<projectDir>/definition/profiles.yaml` | `RB_PROFILES_FILE` | — | C1〜C6 | プロファイル設定ファイル（ページ分割戦略） |
| `host` | string | `127.0.0.1` | `RB_HOST` | `--host` | G5 | preview server の bind アドレス。`0.0.0.0` 等で LAN 公開可 |
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | — | G3 | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用 |
