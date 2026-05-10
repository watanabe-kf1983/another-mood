# Normalizer

## Proposals

### バイナリファイルの正規化 (H1, H2)

`contents_dir` には YAML・Markdown のほかにバイナリファイル（PNG, JPG 等）も配置される想定。バイナリファイルの正規化における扱い（パス解決、Composer への受け渡し等）は未決定。Phase 10 タスク [H1, H2](../../../tasks.md)（仕様確定 + 実装）。

### 散文サブシステムの一般化 (H3)

> **未実装** — Phase 10 タスク [H3](../../../tasks.md)。前提 H1, H2。

内蔵スキーマ `{id, title, body}` は body が Typed Value (`mime_type` + `content`) のため、設計上は既に媒体非依存。バイナリファイル取り扱い (H1/H2) を機に、エンティティ名 `prose` を媒体非依存な名前に改名する。

下位互換のため、旧名 `prose` は内蔵クエリとして残し、`mime_type` が `text/markdown` のレコードのみを供給する案がある。詳細仕様は H1/H2 の進捗に合わせて確定。

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](../../../tasks.md)。
