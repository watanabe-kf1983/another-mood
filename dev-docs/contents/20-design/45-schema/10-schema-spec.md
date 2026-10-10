# Schema Specification

## External Design

### JSON Schema のサブセット

`definition/schema.yaml` は JSON Schema draft 2020-12 のサブセットで書く。削る基準は一つで、**スキーマを検証規則ではなくデータモデルとして読める形に保つ**こと。どの構文も entity と attribute に一つの形・一つの型で落ちる。記法と各キーワードの正本は `docs/reference/schema.md` で、本節はフルセットから何を削ったかだけを並べる（項目ごとの理由と、OpenAPI のスキーマモデルとの違いは[背景](../../90-appendix/20-design/45-schema/10-schema-spec.md)）:

- **単一ファイル・単一ルート** — `$ref` / `$defs` / `$id` などの参照・識別機構を持たない。スキーマの再利用は別スキーマに切り出してキー参照する
- **合成・条件を持たない** — `allOf` / `anyOf` / `oneOf` / `not` / `if` を持たない。型のバリエーションはスキーマ（= テーブル）を分ける
- **`$comment` を持たない** — YAML のコメント構文（`#`）で代替する
- **ルートは record 形** — `properties` + `additionalProperties: false`。ルートの各プロパティが entity になり、map 形はルートに置けない
- **`type` は単一の文字列** — 配列形（`[string, "null"]`）と `null` 型を持たない
- **型の付かない領域を残さない** — 素の `type: object`、`items` の無い `type: array`、宣言した `type` に一致しないリテラルを弾く
- **`x-ref` を足す** — JSON Schema に無い参照整合性制約を拡張キーワードとして加える（後述）

### 参照整合性制約: x-ref

JSON Schema 本体の property 宣言に `x-ref` キーワードを置き、参照先を構造化形式 (`{ entity, attribute }`) で記述する。JSON Schema 2020-12 は未知キーワードを許容するので、純 JSON Schema としての妥当性は保たれる。Snowflake の宣言的 FK と同じアプローチで、最終的な data-level 整合性は **強制せず警告止め** とする。

利用者向けの記法・フィールド・制約・data-level 警告の挙動は `docs/reference/schema.md` の Entity references (x-ref) を正本とする。本節は背後の設計判断に絞る。

#### 書ける位置

プロパティ宣言の直下にだけ x-ref を書ける。さらに以下の制約がある:

- **`type: string` のプロパティのみ**。integer / number / boolean / object / array は meta-schema エラーで拒否
- `items:` 直下 (スカラー配列要素の FK) は meta-schema エラーで拒否

どちらの理由も[背景](../../90-appendix/20-design/45-schema/10-schema-spec.md#x-ref-の背景各論)。

#### 意味論: enum validation framing

参照整合性制約は本質的に **enum validation の動的版** — 「この値は target の集合 (辞書キーの集合 or 指定 attribute の値の集合) に属さねばならない」。この framing で全ケースを一貫的に説明できる:

- Required でない FK の値が省略されている → 適用すべき enum がない → 検査対象外
- 空文字列 → 単なる値、特別扱いしない (target の集合に `""` がなければ違反)
- 自己参照 (e.g. `genres.parent_id` → `genres`) → enum 集合に自身も含まれるだけ、特別ルール不要
- cycle 検出 / cardinality (1:N, N:M) → FK の責務外、別レイヤー
- 多重ターゲット → 当面サポートしない (値依存で参照先が変わるフィールドは `x-ref` を付けない、自由文字列扱い)

#### 実行モード: schema-level はエラー、data-level は警告

参照整合性違反は重大度の階層が異なる。schema-level の不整合は data の読み込み以前に build を止める。data-level は警告として常時検出・常時報告するが、build/watch を止めない (ページは正常レンダリング)。`--strict` フラグは「警告があれば exit non-zero」の意味のみを持つ (検査の ON/OFF ではない)。

x-ref target の許容範囲: ユーザスキーマで宣言された top-level entity と、内蔵 content schema が提供する top-level entity (`prose` / `blob`) のみ。catalog メタデータ (`__definition.*`) は FK 参照の意味を持たないため target から除外する。

## Internal Design

### Entity 名

スキーマから抽出される各エントリは **Entity** と **ObjectType** の 2 階層で表現される。

- **Entity**: データツリー上の到達経路を表す identifier (`id` = access path)。クエリ DSL の `from:`、paging 設定、表示見出しに使う。例: `categories`, `categories.tasks`。アンカーパス（リンク用の実体パス）とは別概念で、こちらは [anchor-spec.md](../70-generator/20-anchor-spec.md) を参照
- **ObjectType**: Entity の中の 1 つの item の型 (`id`)。コレクションを 1 段降りるたびに `.item` を付加する path-based 名。FK 参照や型レベルの cross-reference に使う。例: `categories.item`, `categories.item.tasks.item`

Entity は自身の `item_type` フィールドを通じて ObjectType を保持する。

```yaml
properties:
  categories:                # Entity.id: "categories"
    type: object             # Entity.item_type.id: "categories.item"
    additionalProperties:
      type: object
      properties:
        tasks:               # Entity.id: "categories.tasks"
          type: object       # Entity.item_type.id: "categories.item.tasks.item"
          additionalProperties: { type: object, properties: { ... } }
```

シングルトン (record 形、すなわち `properties` + `additionalProperties: false`) は entity 化されない。シングルトン自身が `object` 型の attribute になり、配下のプロパティが `meta.owner` のようなドット名の attribute として親エンティティに載る。entity 化されるのは collection (`additionalProperties` / `items`) のみで、シングルトン配下の collection はドット名のパスで entity になる (`categories.meta.tasks`)。

データカタログ / メタドキュメンテーション側での扱いは [meta-documentation.md](../20-app/40-meta-documentation.md) 参照。
