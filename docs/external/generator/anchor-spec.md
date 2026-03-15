# Anchor Specification

アンカー（リンク可能なオブジェクト）の識別・マップ構築・リンク解決の仕様。

## ID 体系

Normalizer の正規化により、辞書パターンのオブジェクトには自動的に `id` フィールドが付与される（[schema-spec: 正規化ルール](../normalizer/schema-spec.md#正規化ルール) 参照）。この `id` がアンカーの識別子となる。

- `id`: 正規化で辞書キーから生成される機械的な識別子。英数字・ハイフン・アンダースコアのみ
- `title`: 人間向けの表示名（日本語OK）
- `id` はクラス内でユニーク
- `id` を持つオブジェクトは自動的にフラットアンカーマップに登録される（リンク可能になる）

グローバルにユニークなアンカー ID はエンジンが自動生成する:

- class = ラッパーキーのドット区切りパス（例: `erd`, `erd.entity`）
- アンカー ID = `{class}.{id}`（例: `erd.user-management`, `erd.entity.user`）
- ラッパーキーは**単数形**で記述する

同じ `id` でも異なるクラスなら共存できる:

| アンカー ID | class | id | title |
|---|---|---|---|
| `erd.user-management` | erd | user-management | ユーザー管理の ER図 |
| `erd.entity.user` | erd.entity | user | ユーザー |
| `screen.user` | screen | user | ユーザー画面 |

> **将来課題**: 固定構造オブジェクト（`properties` のみで `additionalProperties` なし）は正規化で `id` が付与されない。シングルトンへのリンクが必要になった場合のアンカー登録方法は別途検討する。

## フラットアンカーマップ

Document Generator が views データのツリーを再帰的に走査し、`id` を持つオブジェクトからフラットマップを自動構築する。

構築手順:

1. ツリー走査 → `id` 持ちオブジェクトのアンカー ID（`{class}.{id}`）を収集
2. paging 設定を適用 → 各アンカーが属するページの href を確定
   - paging に該当するクラス → そのページの href
   - 該当しないクラス → 親を辿って最も近い「ページになるアンカー」の href + `#anchor-id`
3. テンプレートエンジン起動前にマップ構築を完了させる

## リンク解決

### テンプレート内（link_md フィルタ）

```jinja2
{{ "erd.entity.user" | link_md }}
```

→ `[ユーザー](../erd/user-management.md#erd.entity.user)` のような相対リンクを生成。

### Markdown data 内（toc:id 記法）

```markdown
ユーザーの詳細は[ユーザー](toc:erd.entity.user)を参照。
```

エンジンが `toc:erd.entity.user` をフラットマップから解決し、適切な相対パスに置換する。
