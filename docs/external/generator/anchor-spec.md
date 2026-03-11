# Anchor Specification

アンカー（リンク可能なオブジェクト）の識別・マップ構築・リンク解決の仕様。

## key 属性と ID 体系

- `key`: 機械的な識別子。英数字・ハイフン・アンダースコアのみ
- `title`: 人間向けの表示名（日本語OK）
- `key` はクラス内でユニーク
- `key` を持つオブジェクトは自動的にフラットアンカーマップに登録される（リンク可能になる）

グローバルにユニークな ID はエンジンが自動生成する:

- class = ラッパーキーのドット区切りパス（例: `erd`, `erd.entity`）
- ID = `{class}.{key}`（例: `erd.user-management`, `erd.entity.user`）
- ラッパーキーは**単数形**で記述する

同じ `key` でも異なるクラスなら共存できる:

| id | class | key | title |
|---|---|---|---|
| `erd.user-management` | erd | user-management | ユーザー管理の ER図 |
| `erd.entity.user` | erd.entity | user | ユーザー |
| `screen.user` | screen | user | ユーザー画面 |

## フラットアンカーマップ

Document Generator が views データのツリーを再帰的に走査し、`key` を持つオブジェクトからフラットマップを自動構築する。

構築手順:

1. ツリー走査 → `key` 持ちオブジェクトの ID（`{class}.{key}`）を収集
2. paging 設定を適用 → 各アンカーが属するページの href を確定
   - paging に該当するクラス → そのページの href
   - 該当しないクラス → 親を辿って最も近い「ページになるアンカー」の href + `#id`
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
