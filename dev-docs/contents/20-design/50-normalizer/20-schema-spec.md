# Schema Specification

## External Design

### 背景: OpenAPI のスキーマモデルとの違い

> **[W4 → appendix]**

OpenAPI は API 通信プロトコルを記述するため、エンドポイントを流れる**色々な切れ端**それぞれに対応する名前付き型を `components.schemas` に並べる（各エンドポイントから `$ref` で参照する形）。

本ツールが扱うのは API を流れる切れ端ではなく、`contents_dir/` に蓄積された **1 つのデータ総体**である。総体は 1 つのオブジェクトとして表現できるので、それ全体を 1 つの JSON Schema として書く形が自然になる。トップレベルキー (entity 名) は別個の型エントリではなく、ルートオブジェクトの `properties` として並ぶ。

### 背景: なぜサブセットに制限するか

> **[W4 → appendix]** (本節の本文のみ。小節「型の付かない領域を残さない」は残す)

- **`$ref`/`$defs`**: スキーマの再利用が必要な場合、このプロジェクトでは別スキーマに切り出してキー参照する（RDB 的な正規化）。スキーマ内の参照機構は不要
- **合成・条件（`allOf` 等）**: 型のバリエーションはテンプレート記述を複雑にする。バリエーションがあるならスキーマ（= テーブル）を分けるのがこのプロジェクトの方針
- **`$comment`**: YAML のコメント構文（`#`）で代替可能
- **core の残り**: 本ツールは `definition/schema.yaml` を単一の root schema として扱い、外部 schema 参照も想定しないため、`$id` 等の識別機構は不要

#### 型の付かない領域を残さない

> **[W4 dup]** ↔ schema-schema.yaml:189-199,244-251 コメント、schema.md:243 (a/b, 完全)。規則+理由。案?: 規則は docs/meta-schema が正本→削除、理由 2 (スキーマの値がカタログ経由でデータになる) は残す

キーワードの絞り込みと同じ理由で、JSON Schema が許す「型の付かない領域」も残していない。`type: object` は record (`properties` + `additionalProperties: false`) か map (`additionalProperties: <schema>`) のどちらかでなければならず、素の `type: object` は書けない。`enum` / `const` / `default` / `examples` に書くリテラルも、宣言した `type` に一致していなければならない (素の JSON Schema は前者を「充足不能なだけの妥当なスキーマ」として通し、後者 2 つは注釈として検証すらしない)。

理由は 2 つある。

**object 属性は構造化データのためのもの** — 形の定まらないデータは string 属性で持つべきで、object で受けるものではない。素の `type: object` を残すと、その配下だけスキーマ検査が効かない穴が残り続ける。

**スキーマに書いた値もデータになる** — `title` / `description` / `default` / `examples` / `enum` / `const` はデータカタログ構築が値のまま転記し、カタログは永続化されて generator がメタドキュメントを描くときに読み直す ([meta-documentation.md](../20-app/40-meta-documentation.md))。つまりスキーマの値には、データと同じ [JSON データモデル](../40-communication/10-json-data-model.md) の制約が及ぶ。YAML は JSON のスーパーセットなので、型が無制約な場所には YAML ローダが構築した `datetime.date` 等が入りうる。

### 参照整合性制約: x-ref

> **[W4 dup]** ↔ schema.md:193、data_catalog.py XRef、schema-schema.yaml:39-53 (部分)。案: 残す

JSON Schema 本体の property 宣言に `x-ref` キーワードを置き、参照先を構造化形式 (`{ entity, attribute }`) で記述する。JSON Schema 2020-12 は未知キーワードを許容するので、純 JSON Schema としての妥当性は保たれる。Snowflake の宣言的 FK と同じアプローチで、最終的な data-level 整合性は **強制せず警告止め** とする。

利用者向けの記法・フィールド・制約・data-level 警告の挙動は `docs/reference/schema.md` の Entity references (x-ref) を正本とする。本節は背後の設計判断に絞る。

#### 書ける位置

> **[W4 dup]** ↔ schema.md:218、schema-schema.yaml:127-134,178-182 コメント (理由まで) (a/b, 完全)。案: 削除→docs/meta-schema。propertyNames 非サポートの理由はコードに無い→meta-schema コメントへ

> **[W4 → appendix?]** 推奨: 残す (規則は docs にあり残るのは理由だが、normalization contract と跨る)

プロパティ宣言の直下にだけ x-ref を書ける。さらに以下の制約がある:

- **`type: string` のプロパティのみ**。integer / number / boolean / object / array は meta-schema エラーで拒否
- `items:` 直下 (スカラー配列要素の FK) は meta-schema エラーで拒否
- 辞書キー自体に FK を付けるパターン (`propertyNames` に x-ref) はサポートしない

`type: string` 限定の理由: dict-pattern の synthetic id は normalizer が string に揃え ([normalizer.md](10-normalizer.md)「dict-pattern の synthetic id は常に string」)、target attribute 値も string として比較する。integer / number に開放すると「dict キーは str 化されているのに FROM 側は int」など型ミスマッチが事故化する。FK 値の表現として string を強制することで、normalization contract と整合する。実需が薄いという観察 (showcase/music の FK は全て string) も後押し。integer FK が surface したら、synthetic id の型推論機構と合わせて別タスクで開放する。

`items:` 直下の `x-ref` を明示エラーにする理由は、現状のデータカタログがスカラー配列要素のメタ情報を持たない (items-level の validation も同様に脱落している) ためで、catalog 構造の拡張なしには検査が効かない。「JSON Schema が未知キーワードを黙って無視する」挙動に任せると、ユーザは効いていると誤解する。明示エラーにして footgun を避ける。なお、`items: { type: object, properties: { foo: { x-ref: ... } } }` のように items のサブツリーに含まれる通常プロパティの x-ref は許容される (foo は catalog 上で attribute として現れるため)。

辞書キー自体が FK となるパターン (propertyNames に x-ref を書く形) は当面サポートしない。ユーザ言語に `propertyNames` キーワードを追加する負担に対して、現実のスキーマでは「キーは任意の record id、FK は明示プロパティに置く」スタイルが支配的 (showcase/music もこのスタイルで貫かれている) で、実需が乏しいため。必要が surface したら別 Proposal で復活させる。

#### 意味論: enum validation framing

> **[W4 dup]** ↔ data_fk_validator.py (a, 部分: 省略値のみ)。案: 残す

参照整合性制約は本質的に **enum validation の動的版** — 「この値は target の集合 (辞書キーの集合 or 指定 attribute の値の集合) に属さねばならない」。この framing で全ケースを一貫的に説明できる:

- Required でない FK の値が省略されている → 適用すべき enum がない → 検査対象外
- 空文字列 → 単なる値、特別扱いしない (target の集合に `""` がなければ違反)
- 自己参照 (e.g. `genres.parent_id` → `genres`) → enum 集合に自身も含まれるだけ、特別ルール不要
- cycle 検出 / cardinality (1:N, N:M) → FK の責務外、別レイヤー
- 多重ターゲット → 当面サポートしない (値依存で参照先が変わるフィールドは `x-ref` を付けない、自由文字列扱い)

#### 実行モード: schema-level はエラー、data-level は警告

> **[W4 dup]** ↔ schema.md:219-221、cli.md:96-98 (b)、data_fk_validator.py:16-17,48-49、schema_inspector.py:47-48 (a) — 完全。約束。案: 削除→docs。「--strict は検査の ON/OFF ではない」「opt-in で懸念解消」は残す

参照整合性違反は重大度の階層が異なる:

| 階層 | 失敗の性質 | 重大度 |
|---|---|---|
| schema-level コヒーレンス (x-ref の entity/attribute が schema に実在するか) | スキーマが壊れている | **エラー** (build 失敗) — JSON Schema の構造的バリデーション違反と同等 |
| data-level FK 整合性 (各値が target 集合に属するか) | データの整合性違反 | **警告** (`--strict` で exit code 制御) |

schema-level の不整合は data の読み込み以前に build を止める。data-level は警告として常時検出・常時報告するが、build/watch を止めない (ページは正常レンダリング)。`--strict` フラグは「警告があれば exit non-zero」の意味のみを持つ (検査の ON/OFF ではない)。

「TBD だらけの要件定義フェーズに data-level 警告が大量に出てうるさい」懸念は、`x-ref` 自体が property 単位の opt-in であることで自然に解消される。整備が進んだプロパティに `x-ref` を足していけば、足した分だけ検査が始まる。

x-ref target の許容範囲: ユーザスキーマで宣言された top-level entity と、内蔵 content schema が提供する top-level entity (`prose` / `blob`) のみ。catalog メタデータ (`__definition.*`) は FK 参照の意味を持たないため target から除外する。

#### 背景: なぜ参照先を top-level entity のみに限定したか

> **[W4 → appendix]**

x-ref の `entity:` フィールドは top-level entity しか受け付けない。コンポジション (ネスト構造で表現される 1:N) の関係にあるオブジェクトは、定義上、親と一体で扱われるため独立した FK 被参照対象にならない。逆に、ネスト先のオブジェクトが他から参照されるニーズが surface したら、それはコンポジションではなく集約として別 entity に切り出すべきサインで、ネストパス (`screens.buttons.save` 等) を target にする構文拡張ではなく、データモデル側の修正で対応する。

#### 背景: なぜ property 側に置くか

> **[W4 → appendix]**

参照整合性制約は from 側に一方向にかかる非対称な制約であり、SQL の `REFERENCES` 句も from 側のテーブルに宣言する。宣言的スキーマツール (Prisma, Django ORM, SQLAlchemy, GraphQL, Protobuf 等) はほぼ全てフィールドレベルに配置している。「二者関係なので片側に寄せるのは不自然」という当初の懸念は、FK 制約の意味論を見直すと根拠が弱い。

property レベル配置の副次的な利点:

- 関連情報の凝集 — プロパティ宣言と FK 情報を同じ場所で読める
- 同期コストの低下 — プロパティ削除時に FK 宣言も一緒に消える
- AI ヒントとして強い — プロパティ定義の隣に書いてあるため見落としにくい

別ファイル (`references.yaml`) 案や、`schema.yaml` のトップレベルに `references:` を追加する案も検討したが、前者は情報が分散する分の不利、後者は schema.yaml を「JSON Schema として読める」状態から外す不利が property レベル案を上回らなかった。

#### 背景: なぜキーワード名を `x-ref:` にしたか

> **[W4 → appendix]**

`x-` 接頭辞は JSON Schema 2020-12 の規約としては要求されないが、OpenAPI から続く「仕様外拡張」の慣習として広く認知されている。`x-` を付けることで「これは Another Mood 固有の拡張」と一目で分かる。`x-ref:` 自体は短く、ER 用語の "reference" に直結する。

#### 背景: なぜ値を構造化形式にしたか

> **[W4 → appendix]**

文字列パス (`"artists.name"`) より構造化形式 (`{ entity: artists, attribute: name }`) を選んだのは、Schema-Inspector の 1 パス目で entity / attribute の識別を型レベルで保証するため。catalog 構築完了前の段階でも、構文的妥当性は構造から判断できる。target の存在検証は catalog 構築後の遅延処理に分離できる。

## Internal Design

### Entity 名

> **[W4 dup]** ↔ 20-app/40-meta-documentation「Entity と ObjectType」(c, 逐語)、data_catalog.py:146-152,256-267,565-572 (a) — 完全。案: ここを正本、meta-documentation 側をポインタ化

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
