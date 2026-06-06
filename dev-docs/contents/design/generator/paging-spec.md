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

### テンプレート主題のノード受け取りと `this` 束縛

テンプレートの主題（subject）は **データツリーのノード**（Mapping = レコード / Array = コレクション）として渡し、コンテキストに **固定名 `this` で束縛**する:

- **Mapping 主題**: キーを spread し `{{ 名前 }}` で bare アクセス（`this.` 税ゼロ）。加えて `this` も束縛（`{{ this.名前 }}` ≡ `{{ 名前 }}`）
- **非 Mapping 主題（Array）**: spread するフィールドがないので `this` のみ（`{% for e in this %}`）
- スカラ主題は、分割（別ページ書き出し）時のみエラー — ページはアンカー可能なノードであるべきだから。inline 展開は単なる差し込みなので任意の値を許す
- `this` は型不問で **常に主題ノード自身**（`_meta` アクセス・配列反復の handle）

**束縛はレンダリング境界（`template_engine._bind`）の単一規則**として、root テンプレート（`index.md`）と `{% mood_view %}` サブテンプレートに同一に適用する。利用者から見えるデータモデルがツリー全体で一致し、root も自ノードを `this` で参照できる。`{% mood_view %}` 側はパス決定とノードのパススルーだけを担い、context 構築は持たない。

## Proposals

> **部分実装** — Phase 11 タスク [C1〜C6](../../../tasks.md)。C1 で `reports.yaml` の読み込み・形式検証、C2 で `file_per` 評価 (`ReportsConfig.is_split_target`) は完了。以下は評価結果で実際にページ分割を駆動する未実装部分 (C3〜C6)。現在の `{% mood_view %}` は常に分割で、`file_per` 設定はまだ出力に反映されない。

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

ページパスはアンカーパスから直接導出される。導出規則は `ReportsConfig.page_path` (B6) が持ち、その定義は [generator.md](generator.md#ページパスの導出-b6) を正本とする。anchor_path を流用するため、セグメントの**エスケープも anchor_path と同じ IRI 形を継承する**（[anchor-spec.md](anchor-spec.md#escape-規則) — 非 ASCII の `ucschar` は生のまま、`/` 等の構造文字と FS 危険文字は percent-encode）。要点:

- **非 root**: anchor_path の先頭 `/` を落として `.md` を付けたもの（例: `/erds/user-management` → `erds/user-management.md`、`/erds/user-management/entities/user` → `erds/user-management/entities/user.md`、シングルトン `/overview` → `overview.md`）
- **root (`anchor_path == "/"`)**: `index.md` 固定（file_per 不問）

これによりアンカーパス規則と paging path 規則が同じ shape で表現される。

`page_path` (B6, `ReportsConfig.page_path`) は **レポートルート相対**。実ファイルの書き出し位置は、mood_view (C3) が出力ディレクトリ規約のマウント先を被せて決める:

- トップ直書き form: `{outDir}/reports/{page_path}`
- `profiles:` あり: `{outDir}/reports/{profile_name}/{page_path}`

### 分割ルール

- `file_per` に列挙された ObjectType ID が分割単位
- 列挙されていない ObjectType の `{% mood_view %}` はインライン展開される

### `{% mood_view %}` との関係

テンプレートの `{% mood_view %}` タグは `file_per` 設定に応じて振る舞いが変わる:

- 対象ノードの `_meta.object_type_id` が `file_per` の分割単位に含まれる → 別ファイルに出力し、親にはリンクを残す
- 含まれない → インライン展開（通常の `{% include %}` と同等）

テンプレート作者はページ分割を意識しない。同じテンプレートが Web 用（分割）でも PDF 用（全部インライン）でもそのまま動く。

### meta 子テンプレートへの root threading

> P3（`this` 束縛 / 主題ノード受け取り）は実装済み — [テンプレート主題のノード受け取りと `this` 束縛](#テンプレート主題のノード受け取りと-this-束縛) を参照。残るのは出力パス統一（C3）・B4/B5 簡約・meta 子テンプレートへの root threading 解消（E12）。

`this` 束縛で主題がノードになったことを足場に、まだ残る簡約が三つある:

1. **出力パスの page_path 統一（C3）.** 現状の出力パス決定は暫定（id 付き Mapping → `{stem}/{id}.md`、それ以外 → `template_name`）で、anchor map に載らずリンク先として参照しづらい。meta 診断の合成 dict（[E12](../../../tasks.md)）がノード化され全主題がノードになると、C3 が mood_view のパス決定を `ReportsConfig.page_path(node)` 一本に畳める（ページの anchor / page_path が主題ノードの anchor_path で安定し anchor map に載る）。ページ名を「データ名」でなく「ページ概念」にしたい場合は、その名前のビュー（query）を定義する（＝「ディレクトリ名 = ビュー名」と同じ筋）。

2. **B4/B5 の source-node プラミング簡約.** リンク解決の「いま自分はどのページか（source node）」を `this` から取れるので、[generator.md](generator.md#リンク解決-b4-b5) が想定する **per-render の resolver closure-binding（source node 束縛）が不要**になり、resolver は静的な `(ReportsConfig, anchor_map)` だけ束縛すればよくなる（B4/B5 実装時に取り込む）。

3. **meta 子テンプレートへの root threading 解消.** meta 子テンプレート（`__table_view` / `__meta_query`）は `walk_entity` の入力に root の全ビュー集合を要するが、主題が合成 dict（非ツリーノード）で親チェーンを持たないため、`__root.md` が root ノードを `root` キーで明示的に渡している。**E12（meta 診断データを query で実ノード化）**で子が実ノードになれば、親チェーン経由で root に届き、この threading は不要になる。
