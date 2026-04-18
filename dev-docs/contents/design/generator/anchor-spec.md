# Anchor Specification

> **未実装** — Phase 8 タスク [B1〜B6](../../../phase8-tasks.md)（ラッパーツリー / アンカー ID 規則 / オンデマンド走査 / `link_md` フィルタ / `toc:id` 解決 / `get_page_url`）

アンカー（リンク可能なオブジェクト）の識別とリンク解決の仕様。

## ID 体系

正規化後のデータモデル（配列 or オブジェクト）によって、アンカーの識別方法が決まる。

### 配列（リスト型）

Normalizer の正規化により各要素に `id` フィールドが付与される（[schema-spec: 正規化ルール](../normalizer/schema-spec.md#正規化ルール) 参照）。

- class = ラッパーキーのドット区切りパスに `.item` を付加
- アンカー ID = `{class}.{id}`

### オブジェクト（シングルトン型）

単一オブジェクトなので `id` は不要。ラッパーキー自体がアンカーとなる。

- class = ラッパーキーのドット区切りパス
- アンカー ID = `{class}`（class と同一）

### 例

正規化後の views データ:

```yaml
overview:                        # オブジェクト → シングルトン
  title: システム概要

erds:                            # 配列 → リスト
  - id: user-management
    title: ユーザー管理の ER図
    entities:                    # 配列 → リスト（ネスト）
      - id: user
        title: ユーザー
  - id: order-flow
    title: 受注フローの ER図

screens:                         # 配列 → リスト
  - id: user
    title: ユーザー画面

prose:                           # 配列 → リスト（Markdown データソース）
  - id: internal/architecture.md
    title: Architecture
  - id: design/normalizer/schema-spec.md
    title: Schema Specification
```

| アンカー ID | class | id | title |
|---|---|---|---|
| `overview` | overview | *(なし)* | システム概要 |
| `erds.item.user-management` | erds.item | user-management | ユーザー管理の ER図 |
| `erds.item.entities.item.user` | erds.item.entities.item | user | ユーザー |
| `screens.item.user` | screens.item | user | ユーザー画面 |
| `prose.item.internal/architecture.md` | prose.item | internal/architecture.md | Architecture |
| `prose.item.design/normalizer/schema-spec.md` | prose.item | design/normalizer/schema-spec.md | Schema Specification |

- `title`: 人間向けの表示名（日本語OK）
- アンカー ID はグローバル一意とは限らない。リンク対象として使う主要オブジェクトの `id` が実質的にユニークであればよい

## リンク記法

テンプレート内では `link_md` フィルタを使用する:

```jinja2
{{ "erds.item.entities.item.user" | link_md }}
```

Markdown data 内では `toc:` 記法を使用する:

```markdown
ユーザーの詳細は[ユーザー](toc:erds.item.entities.item.user)を参照。
```

Markdown データソースでは、Normalizer がソース内の相対リンクを自動的に `toc:` 記法に変換する（[markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照）:

```markdown
{# ソース: {contents_dir}/internal/normalizer.md #}
[Composer](composer.md)
↓ Normalizer が変換 ↓
[Composer](toc:prose.item.internal/composer.md)
```

## リンク解決

アンカー ID から実際のリンク先 URL への解決は、paging 設定に依存する（[paging-spec](paging-spec.md) 参照）。エンジンがアンカー ID を適切な相対パスに置換する。

→ 例: `[ユーザー](../erds/user-management.md#erds.item.entities.item.user)`
