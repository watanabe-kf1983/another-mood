# Schema Specification (appendix)

[Schema Specification](../../../20-design/45-schema/10-schema-spec.md) の背景。

## OpenAPI のスキーマモデルとの違い

OpenAPI は API 通信プロトコルを記述するため、エンドポイントを流れる**色々な切れ端**それぞれに対応する名前付き型を `components.schemas` に並べる（各エンドポイントから `$ref` で参照する形）。

本ツールが扱うのは API を流れる切れ端ではなく、`contents_dir/` に蓄積された **1 つのデータ総体**である。総体は 1 つのオブジェクトとして表現できるので、それ全体を 1 つの JSON Schema として書く形が自然になる。トップレベルキー (entity 名) は別個の型エントリではなく、ルートオブジェクトの `properties` として並ぶ。

## サブセットに制限する理由（各論）

本文の一覧と同じ順で、項目ごとに削った理由を置く。

### 単一ファイル・単一ルート

- **`$ref`/`$defs`**: スキーマの再利用が必要な場合、このプロジェクトでは別スキーマに切り出してキー参照する（RDB 的な正規化）。スキーマ内の参照機構は不要
- **core の残り**: 本ツールは `definition/schema.yaml` を単一の root schema として扱い、外部 schema 参照も想定しないため、`$id` 等の識別機構は不要

### 合成・条件を持たない

型のバリエーションはテンプレート記述を複雑にする。バリエーションがあるならスキーマ（= テーブル）を分けるのがこのプロジェクトの方針。

### `$comment` を持たない

YAML のコメント構文（`#`）で代替可能。

### ルートは record 形

entity の集合はスキーマの宣言だけで確定させる。ルートの各プロパティがそのまま entity で、カタログもクエリの `from:` もメタドキュメントの目次も、データを読む前にこの集合を知っている。ルートに map 形を許すと entity 名がデータ側で決まることになり、スキーマから起こしたカタログが entity を列挙できない。

### `type` は単一の文字列

attribute には一つの型を持たせる。カタログが attribute ごとに型を一つ記録し、メタドキュメントの型表示・テンプレートのフィルタ・x-ref の比較はそれを前提にする。配列形（`[string, "null"]`）を許すと attribute が型の集合を持つことになり、この前提が崩れる。値が無いことは `required` から外して属性を省略することで表し、`null` 型を別に持たない。

### 型の付かない領域を残さない

素の JSON Schema は、素の `type: object` を「充足不能なだけの妥当なスキーマ」として通し、`enum` / `const` / `default` / `examples` のリテラルは注釈として検証すらしない。このツールが両方を弾く理由は二つある。

**object 属性は構造化データのためのもの** — 形の定まらないデータは string 属性で持つべきで、object で受けるものではない。素の `type: object` を残すと、その配下だけスキーマ検査が効かない穴が残り続ける。

**スキーマに書いた値もデータになる** — `title` / `description` / `default` / `examples` / `enum` / `const` はデータカタログ構築が値のまま転記し、カタログは永続化されて generator がメタドキュメントを描くときに読み直す ([meta-documentation.md](../../../20-design/20-app/40-meta-documentation.md))。つまりスキーマの値には、データと同じ [JSON データモデル](../../../20-design/40-communication/10-json-data-model.md) の制約が及ぶ。YAML は JSON のスーパーセットなので、型が無制約な場所には YAML ローダが構築した `datetime.date` 等が入りうる。

## x-ref の背景（各論）

### なぜ `type: string` のプロパティに限るか

`type: string` 限定の理由: dict-pattern の synthetic id は normalizer が string に揃え ([normalizer.md](../../../20-design/50-normalizer/10-normalizer.md)「dict-pattern の synthetic id は常に string」)、target attribute 値も string として比較する。integer / number に開放すると「dict キーは str 化されているのに FROM 側は int」など型ミスマッチが事故化する。FK 値の表現として string を強制することで、normalization contract と整合する。実需が薄いという観察 (showcase/music の FK は全て string) も後押し。integer FK が surface したら、synthetic id の型推論機構と合わせて別タスクで開放する。

### なぜ `items:` 直下を明示エラーにするか

`items:` 直下の `x-ref` を明示エラーにする理由は、現状のデータカタログがスカラー配列要素のメタ情報を持たない (items-level の validation も同様に脱落している) ためで、catalog 構造の拡張なしには検査が効かない。「JSON Schema が未知キーワードを黙って無視する」挙動に任せると、ユーザは効いていると誤解する。明示エラーにして footgun を避ける。なお、`items: { type: object, properties: { foo: { x-ref: ... } } }` のように items のサブツリーに含まれる通常プロパティの x-ref は許容される (foo は catalog 上で attribute として現れるため)。

### なぜ data-level 警告が洪水にならないか

「TBD だらけの要件定義フェーズに data-level 警告が大量に出てうるさい」懸念は、`x-ref` 自体が property 単位の opt-in であることで自然に解消される。整備が進んだプロパティに `x-ref` を足していけば、足した分だけ検査が始まる。

### なぜ参照先を top-level entity のみに限定したか

x-ref の `entity:` フィールドは top-level entity しか受け付けない。コンポジション (ネスト構造で表現される 1:N) の関係にあるオブジェクトは、定義上、親と一体で扱われるため独立した FK 被参照対象にならない。逆に、ネスト先のオブジェクトが他から参照されるニーズが surface したら、それはコンポジションではなく集約として別 entity に切り出すべきサインで、ネストパス (`screens.buttons.save` 等) を target にする構文拡張ではなく、データモデル側の修正で対応する。

### なぜ property 側に置くか

参照整合性制約は from 側に一方向にかかる非対称な制約であり、SQL の `REFERENCES` 句も from 側のテーブルに宣言する。宣言的スキーマツール (Prisma, Django ORM, SQLAlchemy, GraphQL, Protobuf 等) はほぼ全てフィールドレベルに配置している。「二者関係なので片側に寄せるのは不自然」という当初の懸念は、FK 制約の意味論を見直すと根拠が弱い。

property レベル配置の副次的な利点:

- 関連情報の凝集 — プロパティ宣言と FK 情報を同じ場所で読める
- 同期コストの低下 — プロパティ削除時に FK 宣言も一緒に消える
- AI ヒントとして強い — プロパティ定義の隣に書いてあるため見落としにくい

別ファイル (`references.yaml`) 案や、`schema.yaml` のトップレベルに `references:` を追加する案も検討したが、前者は情報が分散する分の不利、後者は schema.yaml を「JSON Schema として読める」状態から外す不利が property レベル案を上回らなかった。

### なぜキーワード名を `x-ref:` にしたか

`x-` 接頭辞は JSON Schema 2020-12 の規約としては要求されないが、OpenAPI から続く「仕様外拡張」の慣習として広く認知されている。`x-` を付けることで「これは Another Mood 固有の拡張」と一目で分かる。`x-ref:` 自体は短く、ER 用語の "reference" に直結する。

### なぜ値を構造化形式にしたか

文字列パス (`"artists.name"`) より構造化形式 (`{ entity: artists, attribute: name }`) を選んだのは、Schema-Inspector の 1 パス目で entity / attribute の識別を型レベルで保証するため。catalog 構築完了前の段階でも、構文的妥当性は構造から判断できる。target の存在検証は catalog 構築後の遅延処理に分離できる。
