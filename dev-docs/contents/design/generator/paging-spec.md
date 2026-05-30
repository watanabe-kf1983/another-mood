# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割とプロファイル切り替えを定義する。

## Proposals

> **未実装** — Phase 10 タスク [C1〜C6](../../../tasks.md)。現在の `{% mood_view %}` は常に分割で、`paginate` 設定は読まれない。

### レポート設定ファイル

`definition/reports.yaml` でレポート出力を設定する。`paginate` にはページとして切り出す対象 ObjectType ID ([schema-spec.md](../normalizer/schema-spec.md#entity-名) 参照 — 実行時には各ノードの `_meta.object_type_id` ([generator.md](generator.md#ノードメタデータ)) と照合される) を列挙する:

```yaml
# definition/reports.yaml — 単一出力
paginate:
  - erds.item
  - erds.item.entities.item
```

複数バリエーション（Web 版と PDF 版を並行配信する等）が必要な場合は `profiles:` キーで列挙する:

```yaml
# definition/reports.yaml — 複数プロファイル
profiles:
  web:
    paginate:
      - erds.item
      - erds.item.entities.item
  pdf:
    paginate: []              # 分割なし → 全部 index.md にインライン
```

**トップ直書きの形と `profiles:` だけがある形の二択**。両方を混在させる（トップに共通設定を書きつつ `profiles:` でも書く）形は不可とする。

### 出力ディレクトリ規約

レポート出力は `{outDir}/reports/` 配下。`reports.yaml` の形に応じてその下の階層が変わる:

- `reports.yaml` 無し、または `profiles:` キー無し → `{outDir}/reports/index.md`（フラット）
- `profiles:` あり → `{outDir}/reports/{profile_name}/index.md`（プロファイル軸が一段挟まる）

`{outDir}` 直下の診断系出力（`index.md`、`__meta_entity/` 等）はプロファイル横断で常に同じ位置に出る。プロファイル概念は **レポートの中** にのみ存在する。

### パス自動導出

分割対象 ObjectType のページパスはアンカー ID から直接導出される — **アンカー ID に `.md` を付けたものがファイルパス**（[anchor-spec](anchor-spec.md) 参照）:

- リスト要素: `{anchor_id}.md`（例: `erds/user-management.md`、`erds/user-management/entities/user.md`）
- シングルトン: `{anchor_id}.md`（例: `overview.md`）

アンカー ID は `/` 区切りの path 形式なので、そのままファイルシステム上のパスとして使える。これによりアンカー ID 規則と paging path 規則が同じ shape で表現される。

### 分割ルール

- `paginate` に列挙された ObjectType ID が分割単位
- 列挙されていない ObjectType の `{% mood_view %}` はインライン展開される

### `{% mood_view %}` との関係

テンプレートの `{% mood_view %}` タグは `paginate` 設定に応じて振る舞いが変わる:

- 対象ノードの `_meta.object_type_id` が `paginate` の分割単位に含まれる → 別ファイルに出力し、親にはリンクを残す
- 含まれない → インライン展開（通常の `{% include %}` と同等）

テンプレート作者はページ分割を意識しない。同じテンプレートが Web 用（分割）でも PDF 用（全部インライン）でもそのまま動く。
