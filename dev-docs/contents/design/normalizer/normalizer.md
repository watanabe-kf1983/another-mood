# Normalizer

## Internal Design

### 正規化スコープと catalog 境界

正規化スコープは catalog 化スコープと一致させる。境界外で walker が走ると、新規変換の追加で silent に壊れる latent risk が生じる。

- `content_normalizer`: user schema 全体が catalog 範囲 (`iter_normalized` で深く正規化)
- `query_deriver`: top-level dict のみが catalog 範囲 (`_iter_top_level` で dict→list 変換のみ。query body は `parse_query` までパススルー)

## Proposals

### バイナリファイルの正規化 (H1, H2)

`contents_dir` には YAML・Markdown のほかにバイナリファイル（PNG, JPG 等）も配置される想定。バイナリファイルの正規化における扱い（パス解決、Composer への受け渡し等）は未決定。Phase 10 タスク [H1, H2](../../../tasks.md)（仕様確定 + 実装）。

### 散文サブシステムの一般化 (H3)

> **未実装** — Phase 10 タスク [H3](../../../tasks.md)。前提 H1, H2。

内蔵スキーマ `{id, title, body}` は body が Typed Value (`mime_type` + `content`) のため、設計上は既に媒体非依存。バイナリファイル取り扱い (H1/H2) を機に、エンティティ名 `prose` を媒体非依存な名前に改名する。

下位互換のため、旧名 `prose` は内蔵クエリとして残し、`mime_type` が `text/markdown` のレコードのみを供給する案がある。詳細仕様は H1/H2 の進捗に合わせて確定。

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](../../../tasks.md)。

### 正規化スコープと catalog 境界 (M6, M7)

M5 で確立した境界 (Internal Design 参照) を、ad-hoc 実装から schema 上のマーカー駆動の一般機構に置き換える後続段階。

#### 段階 2 (M6): blob marker 機構の導入 (内部 schema 専用)

M5 の ad-hoc な「浅い正規化」を、schema 上のマーカーで表現できる一般機構に置き換える。マーカーを見ると `build_schema_tree` は `BlobNode` (新規) を emit、`normalize_data` はデータをパススルー、というルール。

マーカー syntax の候補:

| 案 | 内容 | 評価 |
|---|---|---|
| `additionalProperties: true` 流用 | JSON Schema 既存語彙の再解釈 | 意味的整合 (extras OK = opaque)。`additionalProperties: <schema>` (dict-pattern) や `false` (strict) との分岐ロジック増 |
| **`x-mood-blob: true` custom annotation** | JSON Schema validator が未知 key として無視 | 意図が surface に出る、独立 semantic、将来拡張余地あり。**本命** |

この段階では `query-schema.yaml` の `whereClause` 等にマーカーを付け、M5 で導入した ad-hoc な浅い正規化 (`_iter_top_level`) を marker 駆動に置き換える。**`schema-schema.yaml` には触れない (内部 schema 専用)**。

具体的な改修対象:

- `schema_tree.py`: マーカー検出時に `BlobNode` を emit、内部再帰なし
- `normalize_core.py`: マーカー検出時はパススルー
- `query-schema.yaml`: `whereClause` 等に `x-mood-blob: true` 付与
- `data_catalog.py`: `BlobNode` の catalog 表現

#### 段階 3 (M7): user schema への解放

M6 の機構を `schema-schema.yaml` の `if/then/else` で user schema からも宣言できるようにする。骨子:

```yaml
$defs:
  maybeBlobOrStrict:
    if:
      type: object
      required: [x-mood-blob]
      properties: { x-mood-blob: { const: true } }
    then:
      $ref: "#/$defs/blobSchema"
    else:
      $ref: "#/$defs/jsonSchemaSubset"

  blobSchema:
    type: object
    required: [type, x-mood-blob]
    properties:
      type: { const: object }
      x-mood-blob: { const: true }
    # additionalProperties 制約を外す → oneOf / $ref 等の JSON Schema 構文を許容
    # → validator は標準通り解釈、walker は opaque

  jsonSchemaSubset:
    # 既存の strict subset、ただし再帰先を maybeBlobOrStrict に切替
    ...
```

メタドキュメント (`__meta_entity`) で blob 属性の表示形式を整え、`docs/reference/schema.md` に解説追加。

実需確認 (showcase / dev-docs での「ここは blob にしたい」具体ニーズ、または user からのリクエスト) が surface してから着手。現時点では明確な user requirement なし、design 議論のみ完了。

#### 走査の非対称性との関係

blob 内部は walker (build_schema_tree, normalize_data, query DSL の参照解決) いずれからも opaque。これは [queries-spec.md「走査の非対称性 (設計原則)」](../composer/queries-spec.md#走査の非対称性-設計原則) の「nested array に潜るのは `flatten:` 系のみ」と同質の制約として扱う。
