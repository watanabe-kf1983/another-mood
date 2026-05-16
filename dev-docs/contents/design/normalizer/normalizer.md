# Normalizer

## Proposals

### バイナリファイルの正規化 (H1, H2)

`contents_dir` には YAML・Markdown のほかにバイナリファイル（PNG, JPG 等）も配置される想定。バイナリファイルの正規化における扱い（パス解決、Composer への受け渡し等）は未決定。Phase 10 タスク [H1, H2](../../../tasks.md)（仕様確定 + 実装）。

### 散文サブシステムの一般化 (H3)

> **未実装** — Phase 10 タスク [H3](../../../tasks.md)。前提 H1, H2。

内蔵スキーマ `{id, title, body}` は body が Typed Value (`mime_type` + `content`) のため、設計上は既に媒体非依存。バイナリファイル取り扱い (H1/H2) を機に、エンティティ名 `prose` を媒体非依存な名前に改名する。

下位互換のため、旧名 `prose` は内蔵クエリとして残し、`mime_type` が `text/markdown` のレコードのみを供給する案がある。詳細仕様は H1/H2 の進捗に合わせて確定。

### Unique 制約 (D8, D9)

追加の Unique 制約（id 以外のフィールドに対する一意性）の宣言。Phase 10 タスク [D8, D9](../../../tasks.md)。

### 正規化スコープと catalog 境界 (M5, M6, M7)

`normalize_data` の walk 範囲と catalog 化される範囲を一致させ、境界を明示する一連のタスク。

#### 背景: 偶然の一致

現状の `normalize_data` は schema-driven に深く再帰するが、query 系では `where:` clause の内部 (and / or / not 等) まで walk する。これは catalog 範囲外にもかかわらず、`_flatten_dict` がそこで発火しないため「結果的に動いている」状態。`normalize_data` に新たな変換が追加されると silent に壊れる latent risk あり。

**原則**: 正規化スコープと catalog 化スコープは一致させる。境界の外は `normalize_data` も `build_schema_tree` も触れない。

#### 段階 1 (M5): 浅い正規化への切り替え

`query_deriver` で `iter_normalized` の利用をやめ、`check` (validate) + top-level dict→list 変換のみに限定。query body の内側 (where / sort / select / join / flatten 等) はパススルー。

動作不変 (現状の `normalize_data` は query body 内で実質何も変換していない)、境界の明文化と latent risk 解消が目的。

#### 段階 2 (M6): blob marker 機構の導入 (内部 schema 専用)

M5 の ad-hoc な「浅い正規化」を、schema 上のマーカーで表現できる一般機構に置き換える。マーカーを見ると `build_schema_tree` は `BlobNode` (新規) を emit、`normalize_data` はデータをパススルー、というルール。

マーカー syntax の候補:

| 案 | 内容 | 評価 |
|---|---|---|
| `additionalProperties: true` 流用 | JSON Schema 既存語彙の再解釈 | 意味的整合 (extras OK = opaque)。`additionalProperties: <schema>` (dict-pattern) や `false` (strict) との分岐ロジック増 |
| **`x-mood-blob: true` custom annotation** | JSON Schema validator が未知 key として無視 | 意図が surface に出る、独立 semantic、将来拡張余地あり。**本命** |

この段階では `query-schema.yaml` の `whereClause` 等にマーカーを付け、M5 の ad-hoc 対応を marker 駆動に置き換える。**`schema-schema.yaml` には触れない (内部 schema 専用)**。

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
