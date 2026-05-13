# Schema Specification

## External Design

### コンポジション vs 集約

YAML はツリー構造を持てるため、1:N の子オブジェクトを必ずしも別スキーマに切り出す必要はない。判断基準は「親を消したら子も消えるか」:

- **コンポジション**（消える）→ ネスト。入れ子の `additionalProperties` も正規化される
- **集約**（消えない）→ 別スキーマ + キー参照（references で定義）

```yaml
# コンポジション: 画面の中のボタンは画面と一体
user-screen:
  title: ユーザー画面
  buttons:
    save:
      label: 保存
      action: save
    cancel:
      label: キャンセル
      action: cancel

# 集約: 注文が参照するユーザーは独立して存在
order-001:
  title: 注文A
  customer: tanaka       # 別スキーマ（users）へのキー参照
```

コンポジションの関係にあるオブジェクトは FK として被参照されない。したがって references の参照先はトップレベルスキーマのみで十分。

### 背景: OpenAPI のスキーマモデルとの違い

OpenAPI は API 通信プロトコルを記述するため、エンドポイントを流れる**色々な切れ端**それぞれに対応する名前付き型を `components.schemas` に並べる（各エンドポイントから `$ref` で参照する形）。

本ツールが扱うのは API を流れる切れ端ではなく、`contents_dir/` に蓄積された **1 つのデータ総体**である。総体は 1 つのオブジェクトとして表現できるので、それ全体を 1 つの JSON Schema として書く形が自然になる。トップレベルキー (entity 名) は別個の型エントリではなく、ルートオブジェクトの `properties` として並ぶ。

### 背景: なぜサブセットに制限するか

- **`$ref`/`$defs`**: スキーマの再利用が必要な場合、このプロジェクトでは別スキーマに切り出してキー参照する（RDB 的な正規化）。スキーマ内の参照機構は不要
- **合成・条件（`allOf` 等）**: 型のバリエーションはテンプレート記述を複雑にする。バリエーションがあるならスキーマ（= テーブル）を分けるのがこのプロジェクトの方針
- **`$comment`**: YAML のコメント構文（`#`）で代替可能
- **core の残り**: 本ツールは `definition/schema.yaml` を単一の root schema として扱い、外部 schema 参照も想定しないため、`$id` 等の識別機構は不要

## Internal Design

### Entity 名

スキーマから抽出される各エントリは **Entity** と **ObjectType** の 2 階層で表現される。

- **Entity**: データツリー上の到達経路を表す identifier (`id` = access path)。クエリ DSL の `from:` や URL/anchor、ファイルパス、表示見出しに使う。例: `categories`, `categories.tasks`
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

シングルトン (`type: object` + `properties` のみ、`additionalProperties` なし) は現状 entity 化されない (親の attribute としてインライン化される)。entity 化されるのは collection (`additionalProperties` / `items`) のみ。

データカタログ / メタドキュメンテーション側での扱いは [meta-documentation.md](../app/meta-documentation.md) 参照。

## Proposals

### `title:` キーワード (M4)

ObjectType に対する人間向けの表示名 (例: `Category`) を `title:` キーワードで指定する仕組み。Phase 10 タスク [M4](../../../tasks.md)。

### 参照整合性制約: references (D1-D7)

> **未実装** — Phase 10 タスク [D1〜D7](../../../tasks.md) で具体化する想定。配置とシンタックスは D1 着手時に再設計するため、以下は議論用の素描。Unique 制約 (D8, D9) は別記、[normalizer.md](normalizer.md) を参照。

参照関係は JSON Schema 本体に埋め込まず、`references` として独立して定義する想定。参照関係は本質的に二者間の関係であり、片側のスキーマに埋め込むのは不自然なため。Snowflake の宣言的 FK と同じアプローチで、制約は**強制しない**。

```yaml
# references.yaml
references:
  - from: orders.customer
    to: users                # users スキーマの .id（省略形）

  - from: orders.assigned_to
    to: users.name           # users スキーマの .name プロパティ
```

#### 構文規則

- `from`: 参照する側。`schema_name.property_name` 形式
- `to`: 参照される側。`schema_name`（.id 省略形）または `schema_name.property_name`
- `to` の省略形 `schema_name` は、`additionalProperties` パターンのスキーマでのみ使用可能（辞書キーから生成される `.id` を参照）
- `type: array` のスキーマを参照する場合はプロパティ名の明示が必須（暗黙の ID がないため）
- **参照先はトップレベルスキーマのみ**。ネストパス（`screens.buttons.save` 等）はサポートしない。コンポジション内の入れ子オブジェクトが被参照される必要が出たら、別スキーマに切り出すべきサイン

#### 辞書キーが FK の場合（propertyNames パターン）

```yaml
# references.yaml
references:
  - from: user-roles          # 辞書キー自体が FK（propertyNames）
    to: users
```

```yaml
# {contents_dir}/user-roles.yaml
user-roles:
  tanaka:                   # ← users.id への参照
    role: admin
  suzuki:                   # ← users.id への参照
    role: member
```

`from` にプロパティ名がない場合、辞書のキー自体が参照であることを示す。

#### 実行時の振る舞い

- 通常モード: 参照整合性チェックを行わない（TBD だらけの要件定義フェーズに配慮）
- `--strict` モード: 整合性を検証し**警告**として報告（CI/リリース時に使用）。エラーではない

#### この宣言が果たす役割

1. **AI へのヒント**: AI がデータ編集時に「このフィールドには users の id が入るべき」と理解できる
2. **ER 図の自動生成**: references からリレーションを読み取り、Mermaid ER 図を描画
3. **影響分析**: 被参照キーを変更しようとした際に「どこから参照されているか」を逆引きで特定できる
4. **リネーム支援**: references に基づいて参照箇所を列挙し、一括置換の漏れを `--strict` で検証できる

### singleton-flatten 内の object[] child entity link を保持する (E10)

> **未実装** — Phase 10 タスク [E10](../../../tasks.md)。

現状 `schema_tree._collect_edges` は singleton ObjectNode の sub-property を `(edge_with_correct_type, dc.Node())` の組で吐き出しており、`object[]` サブプロパティの場合に **child entity link 情報を捨てている**。結果として:

- catalog 上の attribute は `type: object[]` だが `entity: null` になり、独立 entity として登録されない
- query DSL で `from: <singleton>.<collection>` (例: `members.hobby.pets`) が walk 失敗する
- メタドキュメンテーションでも `__meta_entity` / `__table_view` の自動生成対象外となり、table view 列は `[{...}, {...}]` の Python repr として文字列化される

catalog データモデル自体は dotted-name の entity link をサポートしているので (F8 自己記述カタログが手書きで使用、`_MEMBERS_DOTTED_EDGE_YAML` テストフィクスチャ参照)、変換ロジック側を揃えるだけで足りる。

#### 修正方針

`_collect_edges` の singleton 分岐で、sub-property の child node を **構造を保持した形** で吐き出す:

```python
if isinstance(prop.node, ObjectNode):
    yield (_property_to_edge(prop), dc.Node())
    for sub in prop.node.properties:
        # 現状: 常に dc.Node() (= scalar 化、entity link 喪失)
        # 修正後: sub.node に composite child があれば to_catalog_node で構造保持
        yield (
            _property_to_edge(sub, name=f"{prop.name}.{sub.name}"),
            to_catalog_node(sub.node),
        )
```

`to_catalog_node` 自体が ArrayNode → ObjectNode を unwrap してくれるため、`object[]` サブプロパティでは entity link が立ち、scalar サブプロパティでは空 Node のままになる (`to_catalog_node(ValueNode) -> dc.Node()`)。

#### 動作確認用テストデータ

下記スキーマ + データで `members.hobby.pets` が catalog の独立 entity として現れることを期待する:

```yaml
# definition/schema.yaml に追加
members:
  type: object
  additionalProperties:
    type: object
    additionalProperties: false
    properties:
      name:
        type: string
      hobby:
        type: object
        additionalProperties: false
        properties:
          pets:
            type: object
            additionalProperties:
              type: object
              additionalProperties: false
              properties:
                name:
                  type: string
                kind:
                  type: string
```

```yaml
# contents/members.yaml
members:
  alice:
    name: Alice
    hobby:
      pets:
        dog1:
          name: Pochi
          kind: dog
        cat1:
          name: Tama
          kind: cat
```

期待する catalog 出力 (`schema_tree` 修正後):

- `members` entity の attributes に `hobby.pets: object[]` + `entity: members.hobby.pets` + `item_type: members.item.hobby.pets.item` が立つ
- `members.hobby.pets` entity が `parent_entity: members` 付きで登録される
- query DSL で `from: members.hobby.pets` が walk 可能
- `__meta_entity/members.hobby.pets.md` および `__table_view/members.hobby.pets.md` が自動生成される
