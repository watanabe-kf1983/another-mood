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

### mood_view 主題の `this` 束縛 / 非ツリーノードページ / `__views` 退役

> Phase 11 タスク [P3](../../../tasks.md)（`this` 束縛）/ [E12](../../../tasks.md)（meta 診断の query 合成）。C3 と相互作用。

`{% mood_view %}` の主題（subject）を、サブテンプレートのコンテキストに **固定名 `this` で普遍束縛**する（`this` / spread=True で確定）:

- **Mapping 主題**: 従来どおりキーを spread し `{{ 名前 }}` で bare アクセス（`this.` 税ゼロ）。加えて `this` も束縛
- **非 Mapping 主題（ArrayNode 等）**: `this` のみ（`{% for e in this %}`、反復が読みにくければ局所 `{% set xs = this %}`）
- `this` は型不問で **常に主題ノード自身** = `_meta`（anchor_path）アクセス・リンク解決の source・配列反復の handle

**解く問題:**

1. **テンプレ名依存パスの不安定さ.** 現状 mood_view は「合成 dict」を受け取り、出力パスを `{stem}/{id}.md` か `template_name` で決めている（テンプレ名依存・リンク先として参照しづらい）。`this` 束縛は mood_view が **ノードを受け取る**前提なので、ページの anchor / page_path が**主題ノードの anchor_path で安定**し、anchor map にも載って**リンク可能**になる。

   - dev-docs の `tasks.md` 等が `{% set tc = {"categories": categories} %}` と**合成 dict に詰め直している**のは「Jinja の render context は namespace(dict) でなければならず、配列をそのまま context にできない」ための回避策。`categories` は既に anchor `/categories` を持つ ArrayNode なので、ノードのまま渡して `this` で受ければ詰め直しは不要（ページ名を「データ名」でなく「ページ概念」にしたい場合は、その名前のビュー（query）を定義する＝「ディレクトリ名 = ビュー名」と同じ筋）。

2. **B4/B5 の source-node プラミング簡約.** リンク解決の「いま自分はどのページか（source node）」を `this` から取れるので、[generator.md](generator.md#リンク解決-b4-b5) が想定する **per-render の resolver closure-binding（source node 束縛）が不要**になり、resolver は静的な `(ReportsConfig, anchor_map)` だけ束縛すればよくなる。

3. **`__views` の退役.** [generator.py](../../../../src/another_mood/components/generator/generator.py) の `__views` は 2 役 — (1)「現在ノードを値として露出」（root の自己参照）、(2)「子テンプレートが root の全ビュー集合を横断」（meta 診断）。(1) は `this` が一般化し、(2) は **E12（meta 診断データを query で実ノード化）**が引き取る。両者が揃うと `__views` を退役できる。

**naming の根拠**: `this` は指示代名詞で「レコード（`this.名前`）」「コレクション（`for e in this`）」の両役を最も中立にこなす（人称系 `me`/`us` は反復で不格好、`context` は「変数名前空間」の既定語と衝突、`data` は identity を背負う `this._meta` で語義がぼやける）。spread を残すので Mapping の bare アクセスは保たれ、`this` の文字数も問題にならない。

**C3 との関係**: C3 は interim として合成 dict フォールバック（id 付き → `{stem}/{id}.md`、id なし → `template_name`）を持つが、P3 + E12 が揃うと全主題がノード化され、mood_view のパス決定は `page_path(node)` 一本になる。P3 を C3 より先に着地させると C3 が簡潔になる（着手順は要調整）。
