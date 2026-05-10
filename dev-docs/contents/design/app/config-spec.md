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

### 処理対象ディレクトリの CWD 配下制約 (G8)

> **未実装** — タスク [G8](../../../tasks.md)。

`<projectDir>` 引数および `RB_*` で渡されるパスは、CWD 配下のみを許可する。CWD 外のパス（`../other-repo/docs` や絶対パス `/some/elsewhere/docs` 等）はエラーとして拒否する。

現状は `_another_mood_root` ([config.py](../../../../src/another_mood/config.py)) が CWD 外の絶対パスを受けた場合に basename を採用してフォールバックする実装になっており、エラーにはしない。

### 未実装の config キー

| キー | 型 | デフォルト | 環境変数 | CLI | タスク | 説明 |
|------|-----|---------|----------|-----|------|------|
| `profilesFile` | string | `<projectDir>/definition/profiles.yaml` | `RB_PROFILES_FILE` | — | C1〜C6 | プロファイル設定ファイル（ページ分割戦略） |
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | — | G3 | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用 |
