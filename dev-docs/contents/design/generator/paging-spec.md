# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割とプロファイル切り替えを定義する。

## Proposals

> **未実装** — Phase 10 タスク [C1〜C6](../../../tasks.md)。現在の `{% mood_view %}` は常に分割で、`paginate` 設定は読まれない。

### プロファイル設定

`profilesFile`（デフォルト: `docs/definition/profiles.yaml`）にプロファイルごとの設定を定義する。`paginate` にはページとして切り出す対象クラスを列挙する:

```yaml
# {profilesFile}
web:
  paginate:
    - erds.item
    - erds.item.entities.item
pdf:
  paginate: []               # 分割なし → 全部 index.md にインライン
```

### ルートページ

ルートテンプレートの出力先は常に `index.md`（規約、設定不要）。出力ディレクトリはプロファイル名から自動導出される:

- `{outDir}/{profile_name}/index.md`

### パス自動導出

分割対象クラスのページパスはアンカーから直接導出される — **アンカー文字列に `.md` を付けたものがファイルパス**（[anchor-spec](anchor-spec.md) 参照）:

- リスト要素: `{anchor}.md`（例: `erds/user-management.md`、`erds/user-management/entities/user.md`）
- シングルトン: `{anchor}.md`（例: `overview.md`）

アンカーは `/` 区切りの path 形式なので、そのままファイルシステム上のパスとして使える。これにより anchor 規則と paging path 規則が同じ shape で表現される。

### 分割ルール

- `paginate` に列挙されたクラスが分割単位
- 列挙されていないクラスの `{% mood_view %}` はインライン展開される

### `{% mood_view %}` との関係

テンプレートの `{% mood_view %}` タグは `paginate` 設定に応じて振る舞いが変わる:

- 対象クラスが `paginate` の分割単位 → 別ファイルに出力し、親にはリンクを残す
- 分割単位でない → インライン展開（通常の `{% include %}` と同等）

テンプレート作者はページ分割を意識しない。同じテンプレートが Web 用（分割）でも PDF 用（全部インライン）でもそのまま動く。
