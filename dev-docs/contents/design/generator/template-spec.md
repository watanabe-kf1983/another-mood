# Template Specification

## External Design

### 背景: なぜ Undefined をエラーにしないか

Jinja2 は `undefined` クラスを差し替え可能で、厳密な `StrictUndefined`（全ての undefined アクセスでエラー）、チェイン可能な `ChainableUndefined`、デフォルトの `Undefined`（1 階層目はサイレント、チェインはエラー）の 3 段階を提供する。

本プロジェクトは `ChainableUndefined` を採用する。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- デフォルトの `Undefined` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `StrictUndefined` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

## Proposals

### C4 (paginate 自動判定) との関係

C4 では `paginate` 設定を見て `mood_view` が自動的に inline / 分割を判定する予定。`inline` キーワードはその自動判定を上書きする明示指定として P2 で先行実装する。C4 導入後も「常に inline を強制する escape hatch」として残すか、深い統合で吸収するかは C4 実装時に判断。
