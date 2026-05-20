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

シングルトン (`type: object` + `properties` のみ、`additionalProperties` なし) は現状 entity 化されない (親の attribute としてインライン化される)。entity 化されるのは collection (`additionalProperties` / `items`) のみ。なお、シングルトン配下にさらに singleton がネストする場合、2 段以上深い構造は catalog に現れない (1 段平坦化のみ。entity の濫造を避けるための意図的な制限)。

データカタログ / メタドキュメンテーション側での扱いは [meta-documentation.md](../app/meta-documentation.md) 参照。

## Proposals

### `title:` キーワード (M4)

ObjectType に対する人間向けの表示名 (例: `Category`) を `title:` キーワードで指定する仕組み。Phase 10 タスク [M4](../../../tasks.md)。

### 参照整合性制約: x-ref (D1-D7)

> **未実装** — Phase 10 で schema-level の宣言・収集・コヒーレンスチェックまでを [D1〜D5](../../../tasks.md) で実装する想定。data-level の FK 整合性検査と警告インフラ ([D6, D7](../../../tasks.md)) は Phase 11+ に温存。Unique 制約 (D8, D9) は別記、[normalizer.md](normalizer.md) を参照。

JSON Schema 本体の property 宣言 (および `propertyNames`) に `x-ref` キーワードを置き、参照先を構造化形式で記述する。JSON Schema 2020-12 は未知キーワードを許容するので、純 JSON Schema としての妥当性は保たれる。Snowflake の宣言的 FK と同じアプローチで、最終的な data-level 整合性は **強制せず警告止め** とする。

```yaml
albums:
  type: object
  additionalProperties:
    properties:
      artist_id:
        type: string
        x-ref:
          entity: artists           # attribute 省略 = 辞書キー (.id 相当) を参照

      curator:
        type: string
        x-ref:
          entity: users
          attribute: name           # 明示プロパティ参照
```

#### 背景: なぜ property 側に置くか

参照整合性制約は from 側に一方向にかかる非対称な制約であり、SQL の `REFERENCES` 句も from 側のテーブルに宣言する。宣言的スキーマツール (Prisma, Django ORM, SQLAlchemy, GraphQL, Protobuf 等) はほぼ全てフィールドレベルに配置している。「二者関係なので片側に寄せるのは不自然」という当初の懸念は、FK 制約の意味論を見直すと根拠が弱い。

property レベル配置の副次的な利点:

- 関連情報の凝集 — プロパティ宣言と FK 情報を同じ場所で読める
- 同期コストの低下 — プロパティ削除時に FK 宣言も一緒に消える
- AI ヒントとして強い — プロパティ定義の隣に書いてあるため見落としにくい

別ファイル (`references.yaml`) 案や、`schema.yaml` のトップレベルに `references:` を追加する案も検討したが、前者は情報が分散する分の不利、後者は schema.yaml を「JSON Schema として読める」状態から外す不利が property レベル案を上回らなかった。

#### 背景: なぜキーワード名を `x-ref:` にしたか

`x-` 接頭辞は JSON Schema 2020-12 の規約としては要求されないが、OpenAPI から続く「仕様外拡張」の慣習として広く認知されている。`x-` を付けることで「これは Another Mood 固有の拡張」と一目で分かる。`x-ref:` 自体は短く、ER 用語の "reference" に直結する。

#### 背景: なぜ値を構造化形式にしたか

文字列パス (`"artists.name"`) より構造化形式 (`{ entity: artists, attribute: name }`) を選んだのは、Schema-Inspector の 1 パス目で entity / attribute の識別を型レベルで保証するため。catalog 構築完了前の段階でも、構文的妥当性は構造から判断できる。target の存在検証は catalog 構築後の遅延処理に分離できる。

#### 構文規則

- `entity:` 必須 — トップレベル entity 名
- `attribute:` 省略可 — 省略時は「target が辞書キーパターン (`additionalProperties`) の暗黙 .id」を参照する省略形
- 参照先が `type: array` の entity の場合は `attribute:` 必須 (暗黙の id がないため)
- **参照先はトップレベル entity のみ**。ネストパス (`screens.buttons.save` 等) はサポートしない。コンポジション内の入れ子オブジェクトが被参照される必要が出たら、別 entity に切り出すべきサイン

#### 書ける位置

| 位置 | 可否 | 意味 |
|---|---|---|
| プロパティ宣言の直下 | OK | 単一値 FK |
| `propertyNames:` の中 | OK | 辞書キー自体が FK (propertyNames パターン) |
| `items:` の中 | NG (meta-validation エラー) | スカラー配列要素の FK。当面サポートしない (後述) |

辞書キー FK (propertyNames パターン):

```yaml
user-roles:
  type: object
  propertyNames:
    x-ref:
      entity: users
  additionalProperties: { ... }
```

`items:` 配下の `x-ref` を明示エラーにする理由は、現状のデータカタログがスカラー配列要素のメタ情報を持たない (items-level の validation も同様に脱落している) ためで、catalog 構造の拡張なしには検査が効かない。「JSON Schema が未知キーワードを黙って無視する」挙動に任せると、ユーザは効いていると誤解する。明示エラーにして footgun を避ける。

#### 意味論: enum validation framing

参照整合性制約は本質的に **enum validation の動的版** — 「この値は target の集合 (辞書キーの集合 or 指定 attribute の値の集合) に属さねばならない」。この framing で全ケースを一貫的に説明できる:

- Required でない FK の値が省略されている → 適用すべき enum がない → 検査対象外
- 空文字列 → 単なる値、特別扱いしない (target の集合に `""` がなければ違反)
- 自己参照 (e.g. `genres.parent_id` → `genres`) → enum 集合に自身も含まれるだけ、特別ルール不要
- cycle 検出 / cardinality (1:N, N:M) → FK の責務外、別レイヤー
- 多重ターゲット → 当面サポートしない (値依存で参照先が変わるフィールドは `x-ref` を付けない、自由文字列扱い)

#### 実行モード: schema-level はエラー、data-level は警告

参照整合性違反は重大度の階層が異なる:

| 階層 | 失敗の性質 | 重大度 |
|---|---|---|
| schema-level コヒーレンス (x-ref の entity/attribute が schema に実在するか) | スキーマが壊れている | **エラー** (build 失敗) — JSON Schema の構造的バリデーション違反と同等 |
| data-level FK 整合性 (各値が target 集合に属するか) | データの整合性違反 | **警告** (`--strict` で exit code 制御) |

schema-level の不整合は data の読み込み以前に build を止める。data-level は警告として常時検出・常時報告するが、build/watch を止めない (ページは正常レンダリング)。`--strict` フラグは「警告があれば exit non-zero」の意味のみを持つ (検査の ON/OFF ではない)。

「TBD だらけの要件定義フェーズに data-level 警告が大量に出てうるさい」懸念は、`x-ref` 自体が property 単位の opt-in であることで自然に解消される。整備が進んだプロパティに `x-ref` を足していけば、足した分だけ検査が始まる。

#### この宣言が果たす役割

1. **ER 図の自動生成** — references からリレーションを読み取り、Mermaid ER 図を描画 ([F4](../../../tasks.md))
2. **AI へのヒント** — AI がデータ編集時に「このフィールドには users の id が入るべき」と理解できる
3. **影響分析** — 被参照キーを変更しようとした際に「どこから参照されているか」を逆引きで特定できる
4. **リネーム支援** — references に基づいて参照箇所を列挙し、一括置換の漏れを検証できる
5. **(将来) 参照整合性検証** — data-level の dangling 参照を `--strict` 連動で警告

#### データカタログ表現 (D2)

x-ref の収集後、Schema-Inspector は `Attribute` (data_catalog.py) に FK 宣言フィールドを載せる形でカタログへ反映する。これで D6 の data-level 検証も F4/F5 のリレーション描画も、同じカタログを単一の真実として消費できる。

##### Attribute への x_ref フィールド追加

```python
@dataclass(frozen=True)
class XRef:
    entity: str                     # target entity id
    attribute: str | None = None    # target attribute name; None = 暗黙の .id

@dataclass(frozen=True)
class Attribute:
    id: str
    type: str
    required: bool
    metadata: ...
    validation: ...
    child_entity: str | None = None       # 既存 'entity' を改名 (下記)
    child_item_type: str | None = None    # 既存 'item_type' を改名 (下記)
    x_ref: XRef | None = None             # 新規: FK 宣言
```

##### 背景: 既存フィールドの改名

`Attribute.entity` / `Attribute.item_type` は **catalog ツリー上の子 entity へのナビゲーション** (この attribute を辿ると子 entity に降りる) を表す枠で、FK target とは別概念。新規 `x_ref.entity` (FK 対象) と既存 `entity` を同名で並べると混同を招くため、既存を `child_entity` / `child_item_type` に改名する (`Entity.parent_entity` と呼応する命名)。

##### propertyNames FK の取り回し

辞書キー自体が FK のケースは、`_build_array_from_additional` で合成される **暗黙の `.id` Attribute に `x_ref` を載せる** 形に落ちる。これで「辞書キー FK」と「明示プロパティ FK」が同じ表現に揃い、D6 の検証側も F4/F5 の描画側も分岐なしで扱える。

```yaml
# schema (user-authored):
user-roles:
  type: object
  propertyNames:
    x-ref: { entity: users }
  additionalProperties: { ... }
```

```python
# catalog 表現 (Schema-Inspector 後):
Attribute(id="id", type="string", required=True,
          x_ref=XRef(entity="users"))
```

##### 自己記述カタログへの反映

`Attribute.catalog` (F8 で導入された catalog の自己記述 Node) に x_ref の三辺を追加。Entity.item_type の singleton-flatten 規約に準拠して sub-edges まで enumerate する (DSL からは `attr.x_ref.entity` で参照可能になる):

```python
Attribute.catalog = Node(
    children=[
        ...,
        (Edge(name="x_ref", type="object", required=False), Node()),
        (Edge(name="x_ref.entity", type="string", required=False), Node()),
        (Edge(name="x_ref.attribute", type="string", required=False), Node()),
    ],
)
```

##### 想定される消費パターン

**D6 (data-level 検証)** — 属性を走査して x_ref を見つけたら target 集合と照合:

```python
for entity in catalog:
    for attr in entity.item_type.attributes:
        if attr.x_ref:
            check_fk(entity, attr, attr.x_ref, data)
```

**F4 / F5 (ER 図 / DFD)** — DSL クエリで relations を組み立てる:

```yaml
relations:
  from: __definition.entities
  flatten:
    of: item_type.attributes
    as: attr
  where:
    attr.x_ref: { exists: true }
  select:
    - { item: id, as: from_entity }
    - { item: attr.id, as: from_attribute }
    - { item: attr.x_ref.entity, as: to_entity }
    - { item: attr.x_ref.attribute, as: to_attribute }
```

関係一覧 (`__definition.references` のような派生 entity) を built-in に追加する案も考えられるが、上のクエリで十分書ける範囲なので、現段階ではテンプレート側に局所化する。汎用化したくなったら後で built-in に昇格する。

#### 実装スコープの段階

##### Phase 10: schema-level (D1-D5)

x-ref の宣言を受理し、schema レベルの一貫性を検査する段階。[F4 (ER 図)](../app/meta-documentation.md#er-図-f4) の前提となる最小スコープ。

- **D1**: Meta-schema 拡張 — `x-ref` を property 直下と `propertyNames` の中で受理。`items:` 配下は明示エラー
- **D2**: Schema-Inspector 拡張 — traversal 中に (path, x-ref) ペアを収集してデータカタログに反映
- **D3**: Schema-level コヒーレンスチェック — `x-ref.entity` の存在、`x-ref.attribute` の target ObjectType 内存在を検証。違反はエラー (build 失敗)
- **D4**: showcase/music への x-ref 適用 — 実際の入出力例として動作確認
- **D5**: docs/reference 同期 — `schema.md` 等に x-ref キーワードの仕様を反映

##### Phase 11+: data-level (D6, D7)

実データを target 集合と照合する段階。

- **D6**: Data-level FK 整合性検査 — 各データ値が target の集合に属するかを normalizer / validator で検証。違反は警告レベル
- **D7**: 警告インフラ — BuildReport の warning フィールド、`output/__meta_*/` 配下の診断ページ、CLI `--strict` フラグの exit code 制御

D6 の検証結果に source position を付ける実装は、`position_resolver` で path から遅延解決する形でよい。Schema-Inspector が x-ref 収集時に保持する path をそのまま使い回す。

#### 別軸の将来検討

- **トップページへの警告バナー** — テンプレート側に「警告あり / 一覧へのリンク」を渡す機構。templates 拡張が必要なため別タスク
- **query DSL `join` との統合** — `on:` の自動推定や整合チェック。join の利用パターンが見えてから設計
- **スカラー配列要素の FK** — `items:` 配下に `x-ref` を書けるようにする。データカタログの構造拡張が必要なため、items-level の `enum` 等のメタ情報を一斉に扱う改修と合わせて検討

