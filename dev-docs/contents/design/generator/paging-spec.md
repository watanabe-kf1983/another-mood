# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割とプロファイル切り替えを定義する。

## External Design

### レポート設定ファイル

`definition/reports.yaml` でレポート出力を設定する。`schema.yaml` と並ぶ必須ファイル。`mood init` および各 blueprint が生成する。

`file_per` にはページとして切り出す対象 ObjectType ID ([schema-spec.md](../normalizer/schema-spec.md#entity-名) 参照 — 実行時には各ノードの `_meta.object_type_id` ([generator.md](generator.md#ノードメタデータ)) と照合される) を列挙する:

```yaml
# definition/reports.yaml
file_per:
  - erds.item
  - erds.item.entities.item
```

形式検証は内蔵の `reports-schema.yaml` で行う。

## Proposals

> **部分実装** — Phase 11 タスク [C1〜C6](../../../tasks.md)。C1 で `reports.yaml` の読み込み・形式検証は完了。以下は `file_per` 設定を実際に評価してページ分割を駆動する未実装部分。現在の `{% mood_view %}` は常に分割で、`file_per` 設定は読まれない。

### 複数プロファイル

複数バリエーション（Web 版と PDF 版を並行配信する等）を 1 プロジェクトから出すために、`profiles:` キーで列挙する形を追加する:

```yaml
# definition/reports.yaml — 複数プロファイル
profiles:
  web:
    file_per:
      - erds.item
      - erds.item.entities.item
  pdf:
    file_per: []              # 分割なし → 全部 index.md にインライン
```

**トップ直書きの形と `profiles:` だけがある形の二択**。両方を混在させる（トップに共通設定を書きつつ `profiles:` でも書く）形は不可とする。

### 出力ディレクトリ規約

レポート出力は `{outDir}/reports/` 配下。`reports.yaml` の形に応じてその下の階層が変わる:

- トップ直書き form (`profiles:` キー無し) → `{outDir}/reports/index.md`（フラット）
- `profiles:` あり → `{outDir}/reports/{profile_name}/index.md`（プロファイル軸が一段挟まる）

`{outDir}` 直下の診断系出力（`index.md`、`__meta_entity/` 等）はプロファイル横断で常に同じ位置に出る。プロファイル概念は **レポートの中** にのみ存在する。

### パス自動導出

分割対象 ObjectType のページパスはアンカーパスから直接導出される — **アンカーパスに `.md` を付けたものがファイルパス**（[anchor-spec](anchor-spec.md) 参照）:

- リスト要素: `{anchor_path}.md`（例: `/erds/user-management.md`、`/erds/user-management/entities/user.md`）
- シングルトン: `{anchor_path}.md`（例: `/overview.md`）

アンカーパスは root を `/` とする絶対パス形式なので、先頭の `/` を out_dir 起点とみなして解決する（`out_dir` への join 時に先頭 `/` を除く）。これによりアンカーパス規則と paging path 規則が同じ shape で表現される。

### 分割ルール

- `file_per` に列挙された ObjectType ID が分割単位
- 列挙されていない ObjectType の `{% mood_view %}` はインライン展開される

### `{% mood_view %}` との関係

テンプレートの `{% mood_view %}` タグは `file_per` 設定に応じて振る舞いが変わる:

- 対象ノードの `_meta.object_type_id` が `file_per` の分割単位に含まれる → 別ファイルに出力し、親にはリンクを残す
- 含まれない → インライン展開（通常の `{% include %}` と同等）

テンプレート作者はページ分割を意識しない。同じテンプレートが Web 用（分割）でも PDF 用（全部インライン）でもそのまま動く。
