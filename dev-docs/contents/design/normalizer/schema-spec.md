# Schema Specification

## External Design

### 背景: OpenAPI のスキーマモデルとの違い

OpenAPI は API 通信プロトコルを記述するため、エンドポイントを流れる**色々な切れ端**それぞれに対応する名前付き型を `components.schemas` に並べる（各エンドポイントから `$ref` で参照する形）。

本ツールが扱うのは API を流れる切れ端ではなく、`contents_dir/` に蓄積された **1 つのデータ総体**である。総体は 1 つのオブジェクトとして表現できるので、それ全体を 1 つの JSON Schema として書く形が自然になる。トップレベルキー (entity 名) は別個の型エントリではなく、ルートオブジェクトの `properties` として並ぶ。

### 背景: なぜサブセットに制限するか

- **`$ref`/`$defs`**: スキーマの再利用が必要な場合、このプロジェクトでは別スキーマに切り出してキー参照する（RDB 的な正規化）。スキーマ内の参照機構は不要
- **合成・条件（`allOf` 等）**: 型のバリエーションはテンプレート記述を複雑にする。バリエーションがあるならスキーマ（= テーブル）を分けるのがこのプロジェクトの方針
- **`$comment`**: YAML のコメント構文（`#`）で代替可能
- **core の残り**: 本ツールは `definition/schema.yaml` を単一の root schema として扱い、外部 schema 参照も想定しないため、`$id` 等の識別機構は不要

### 参照整合性制約: x-ref

JSON Schema 本体の property 宣言に `x-ref` キーワードを置き、参照先を構造化形式で記述する。JSON Schema 2020-12 は未知キーワードを許容するので、純 JSON Schema としての妥当性は保たれる。Snowflake の宣言的 FK と同じアプローチで、最終的な data-level 整合性は **強制せず警告止め** とする。

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

#### 書ける位置

プロパティ宣言の直下にだけ x-ref を書ける。さらに以下の制約がある:

- **`type: string` のプロパティのみ**。integer / number / boolean / object / array は meta-schema エラーで拒否
- `items:` 直下 (スカラー配列要素の FK) は meta-schema エラーで拒否
- 辞書キー自体に FK を付けるパターン (`propertyNames` に x-ref) はサポートしない

`type: string` 限定の理由: dict-pattern の synthetic id は normalizer が string に揃え ([normalizer.md](normalizer.md)「dict-pattern の synthetic id は常に string」)、target attribute 値も string として比較する。integer / number に開放すると「dict キーは str 化されているのに FROM 側は int」など型ミスマッチが事故化する。FK 値の表現として string を強制することで、normalization contract と整合する。実需が薄いという観察 (showcase/music の 7 FK は全て string) も後押し。integer FK が surface したら、synthetic id の型推論機構と合わせて別タスクで開放する。

`items:` 直下の `x-ref` を明示エラーにする理由は、現状のデータカタログがスカラー配列要素のメタ情報を持たない (items-level の validation も同様に脱落している) ためで、catalog 構造の拡張なしには検査が効かない。「JSON Schema が未知キーワードを黙って無視する」挙動に任せると、ユーザは効いていると誤解する。明示エラーにして footgun を避ける。なお、`items: { type: object, properties: { foo: { x-ref: ... } } }` のように items のサブツリーに含まれる通常プロパティの x-ref は許容される (foo は catalog 上で attribute として現れるため)。

辞書キー自体が FK となるパターン (propertyNames に x-ref を書く形) は当面サポートしない。ユーザ言語に `propertyNames` キーワードを追加する負担に対して、現実のスキーマでは「キーは任意の record id、FK は明示プロパティに置く」スタイルが支配的 (showcase/music もこのスタイルで貫かれている) で、実需が乏しいため。必要が surface したら別 Proposal で復活させる。

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

x-ref target の許容範囲: ユーザスキーマで宣言された top-level entity と、内蔵 content schema が提供する top-level entity (現状は `prose`) のみ。catalog メタデータ (`__definition.*`) は FK 参照の意味を持たないため target から除外する。

#### この宣言が果たす役割

1. **ER 図の自動生成** — references からリレーションを読み取り、Mermaid ER 図を描画 ([F4](../../../tasks.md))
2. **AI へのヒント** — AI がデータ編集時に「このフィールドには users の id が入るべき」と理解できる
3. **影響分析** — 被参照キーを変更しようとした際に「どこから参照されているか」を逆引きで特定できる
4. **リネーム支援** — references に基づいて参照箇所を列挙し、一括置換の漏れを検証できる
5. **(将来) 参照整合性検証** — data-level の dangling 参照を `--strict` 連動で警告

#### 背景: なぜ参照先を top-level entity のみに限定したか

x-ref の `entity:` フィールドは top-level entity しか受け付けない。コンポジション (ネスト構造で表現される 1:N) の関係にあるオブジェクトは、定義上、親と一体で扱われるため独立した FK 被参照対象にならない。逆に、ネスト先のオブジェクトが他から参照されるニーズが surface したら、それはコンポジションではなく集約として別 entity に切り出すべきサインで、ネストパス (`screens.buttons.save` 等) を target にする構文拡張ではなく、データモデル側の修正で対応する。

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

### 参照整合性違反の警告インフラ (D7)

> D6 (data-level FK 検査) は実装済み。x-ref キーワード本体の仕様と振る舞いは External Design 参照。Unique 制約 (D8, D9) は別記、[normalizer.md](normalizer.md) を参照。

BuildReport の warning フィールド、`output/__meta_*/` 配下の診断ページ、CLI `--strict` フラグの exit code 制御を整える。D6 違反を表出するチャネル群。

現状、D6 の FK 違反は schema-level コヒーレンス違反 (D3) と同じ build エラー扱いで後続処理を中止している。D7 で warning インフラが整った時点で、本来の重大度 (警告レベル: build/watch を止めない、`--strict` で exit code 制御のみ) に降ろす。

#### 別軸の将来検討

- **トップページへの警告バナー** — テンプレート側に「警告あり / 一覧へのリンク」を渡す機構。templates 拡張が必要なため別タスク
- **query DSL `join` との統合** — `on:` の自動推定や整合チェック。join の利用パターンが見えてから設計
- **スカラー配列要素の FK** — `items:` 配下に `x-ref` を書けるようにする。データカタログの構造拡張が必要なため、items-level の `enum` 等のメタ情報を一斉に扱う改修と合わせて検討

