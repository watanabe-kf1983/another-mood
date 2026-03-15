# Anchor Specification

アンカー（リンク可能なオブジェクト）の識別・マップ構築・リンク解決の仕様。

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
```

| アンカー ID | class | id | title |
|---|---|---|---|
| `overview` | overview | *(なし)* | システム概要 |
| `erds.item.user-management` | erds.item | user-management | ユーザー管理の ER図 |
| `erds.item.entities.item.user` | erds.item.entities.item | user | ユーザー |
| `screens.item.user` | screens.item | user | ユーザー画面 |

- `id` はクラス内でユニーク
- `title`: 人間向けの表示名（日本語OK）
- 同じ `id` でも異なるクラスなら共存できる（例: `erds.item.entities.item.user` と `screens.item.user`）

## フラットアンカーマップ

Document Generator が views データのツリーを再帰的に走査し、アンカー対象オブジェクトからフラットマップを自動構築する。

アンカー対象:
- リスト型の各要素（`id` を持つオブジェクト）
- シングルトン型のオブジェクト

構築手順:

1. ツリー走査 → アンカー対象オブジェクトのアンカー ID を収集
2. paging 設定を適用 → 各アンカーが属するページの href を確定
   - paging に該当するクラス → そのページの href
   - 該当しないクラス → 親を辿って最も近い「ページになるアンカー」の href + `#anchor-id`
3. テンプレートエンジン起動前にマップ構築を完了させる

## リンク解決

### テンプレート内（link_md フィルタ）

```jinja2
{{ "erds.item.entities.item.user" | link_md }}
```

→ `[ユーザー](../erds/user-management.md#erds.item.entities.item.user)` のような相対リンクを生成。

### Markdown data 内（toc:id 記法）

```markdown
ユーザーの詳細は[ユーザー](toc:erds.item.entities.item.user)を参照。
```

エンジンが `toc:erds.item.entities.item.user` をフラットマップから解決し、適切な相対パスに置換する。
