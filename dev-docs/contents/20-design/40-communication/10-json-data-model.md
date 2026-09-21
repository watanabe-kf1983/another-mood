# JSON データモデル

## Internal Design

### 定義

YAML DSL やテンプレートエンジンが操作する対象は「JSON データモデル」（object / array / string / number / boolean / null で構成されるツリー構造）である。JSON というシリアライズ形式とは無関係で、YAML から読み込んだデータに対しても同様に動作する。

Normalizer から Document Generator まで、全コンポーネントがこのデータモデル上で一貫して動作する。

なお、「JSON データモデル」という用語に対応する正式な仕様は存在しない（XML には XML Information Set という W3C 勧告があるが、JSON にはそれに相当するものがない）。CBOR の RFC 8949 が "the JSON data model" という表現を使用しており、本プロジェクトでもこれに倣う。

YAML のデータモデルは JSON データモデルのスーパーセット（日付型、整数/浮動小数の区別、アンカー等）だが、このアプリで扱うデータは JSON データモデルの範囲内に収まる。

### シリアライズ形式

このプロジェクトが読み書きするファイルは 3 系統あり、系統ごとにシリアライズ形式が決まる。

| 系統 | 例 | 形式 | 読み書き |
|---|---|---|---|
| (1) ユーザ入力 | `contents/*.yaml`、`contents/*.json`、`definition/schema.yaml`、`reports.yaml`、`sbdb.yaml` | YAML 1.2 / JSON | `parse_mapping` |
| (2) 内蔵スキーマリソース | `resources/schemas/*.yaml` | YAML 1.2 | `load_schema` |
| (3) ステージ間中間表現 | tmp 配下の各ステージ出力、`__build_report` | JSON | `load_model` / `save_model` |

**YAML を 1.2 とする理由** ((1) (2) に適用):

- ブール値が `true`/`false` のみに限定される。1.1 で問題になる `yes`/`no`/`on`/`off` の意図せぬブール化（通称 Norway 問題: `country: NO` がブール `False` になる）を回避できる。
- 全ての JSON ドキュメントが valid YAML 1.2 ドキュメントとなる。(1) で JSON 入力を受けるのに追加の parser を要さない。
- ruamel.yaml の既定が 1.2。`version` 指定が不要。

**中間表現を JSON とする理由** ((3) に適用):

ビルド時間のうち ruamel.yaml が支配的だったため。差し替え前の `mood build dev-docs` は 2.67 s、うち中間表現の read/write が cProfile 下で 3.3 s（総 6.07 s の 54%）を占めていた。JSON へ差し替えた後は 1.79 s。tmp 配下は外部契約ではないので、変更は内部に閉じる。

PyYAML の CSafeLoader/Dumper (libyaml) なら YAML のまま 15 倍速くなるが採らない。PyYAML は YAML 1.1 なので、上記の 1.2 を選んだ理由がそのまま失われる。JSON はその曖昧さが構造的に無い。pickle / marshal も計測したが load はほぼ同速（差は 1 ms 未満）で、可読性を失うだけ。

代償は複数行文字列の可読性。YAML の literal block scalar に相当する規約が JSON に無いため、`\n` エスケープの 1 行になり post-mortem 時に読みにくい。`indent=2` と `ensure_ascii=False` で構造と非 ASCII 文字の可読性は保つ。

中間表現に非 JSON 値（日付等）が到達すると `json.dumps` が `TypeError` を投げる。到達経路はスキーマ言語の側で塞いである（[schema-spec.md](../50-normalizer/20-schema-spec.md#型の付かない領域を残さない)）。

#### ファイル名の規約

中間表現のファイル名は、元ソースの名前に `.json` を **追記** する（置換しない）。`foo.yaml` / `foo.yml` / `foo.json` / `foo.md` が同じ出力先に衝突しないようにするため。データカタログもこれに倣い、`schema.yaml` から `schema.yaml.json` を書く。

### 配列内オブジェクトのフィールド統一

Normalizer およびコンポーネントが出力する配列内のオブジェクトは、原則として全て共通するフィールドを持つ。ただし、nullable な項目（スキーマ上 `required` でない項目）は、値が存在しない場合はフィールド自体を省略する（null を補完しない）。

理由: Jinja2 のデフォルト設定では、未定義のフィールドへのアクセスはエラーにならず空文字として描画される。一方 null が入っている場合は `"None"` という文字列が描画されてしまう。また、null を補完しても `None.child` のようなネストアクセスのエラーは防げず、`dict.get("key", {})` によるフォールバックも null が入ると効かなくなる。フィールドが存在しない方がテンプレート側で扱いやすい。

なお、Generator がアンカーパス解決等のためにノードへメタ情報注入を行う仕組み（[generator.md](../70-generator/10-generator.md#ノードメタデータ) 参照）に、スキーマ情報に基づく未定義フィールドアクセスの検知（typo 検出）を相乗りさせて実現できる可能性がある。

### 予約プレフィックス

JSON データモデル上のオブジェクトキーに、以下のプレフィックスを予約する。ユーザ定義のフィールド名にこれらのプレフィックスは使用できない。

| プレフィックス | 用途 | 例 |
|---|---|---|
| `_`（単一） | 将来の拡張用に予約。現時点では使用箇所なし | — |
| `__`（二重） | システム内部フィールド（ユーザは直接扱わない） | `__build_report` |

`__` プレフィックスのフィールドはパイプライン基盤が使用し、ユーザのテンプレートやクエリからは参照しない。`_` プレフィックスは将来ユーザ空間とシステム空間が混在する場面に備えて予約する（Generator が注入する `_parent` / `_parent_record` / `_meta` 等、[generator.md](../70-generator/10-generator.md#ノードメタデータ) 参照）。

内蔵 prose スキーマのキー名 `prose` はプレフィックスなしで維持する。ユーザ定義との衝突が問題になった場合は、設定によるキー名変更で対応する。

### マージ戦略

実装は `json_data_model.py` の `deep_merge` を参照。

## Proposals

### 未決事項

- **トップレベルスキーマが `type: array`（additionalProperties でない）の場合**: id を持たない配列のマージ・重複検出をどうするか未定
- **スキーマ名重複**: 複数スキーマファイルに同じトップレベルキーがあった場合の扱い（エラーとする想定だが未確定）

### データキーにドットを含めない (E14)

view の別名スロット（`select[].as` / `flatten.as` / `join.as` / `grouped.by` 等）は現在、ドットを含む文字列をそのままレコードのキーにする。データにドット入りキーを生む経路はこれだけで、`contents/` 由来のキーは schema.yaml の識別子パターンで縛られている。このため `pluck` は longest-first 照合（キー全体を試してから末尾セグメントを削って降りる）を持ち、カタログの `Attribute.id` のドットは singleton 平坦化（入れ子）かリテラルキーか区別できない。

**案**: DSL の名前を読みも書きもパスとして統一し、データキーにドットを含めない不変条件を立てる。`pluck` は素朴な `split(".")` に戻し、カタログのドットは必ず入れ子を意味する（旧案の `parent_attribute` 追加は不要になる）。設計の本体は [query-dsl-spec.md](../60-composer/10-query-dsl-spec.md#ドット名の意味論統一-e14-e15)。実装後、不変条件はこのファイルの Internal Design に移す。

### ルート Entity の導入 (M13)

フラットカタログ（Entity の列）にルートオブジェクト自身を表すレコードが無い。`collect_entities` はトップレベルの非 collection を黙って落とすが、schema-schema はトップレベルに singleton object / scalar / scalar array をすべて許し、データは normalize → compose → tap / テンプレートまで素通しする。結果、「データは存在するのに view からは `unknown source`、カタログ・meta ページには不可視」という三層のねじれがある（実証済み）。しかも singleton object は docs/reference/schema.md が「Single-record pattern」として三パターンの一つに数える正規の書き方であり、この穴はエッジケースの濫用ではなく文書化済み機能の不可視性である。`__definition` 自身も同じ穴にいる: `__definition.entities` というルートレベルのドット付き id が親無しでぶら下がり、`__definition` の下に入れ子であることを示す情報がカタログに無い。

**案**: 予約 id（`__root` 等。`__` 接頭辞はユーザ名から保護済み）でルートの Entity を一件 emit し、`item_type.attributes` にトップレベルの全キーを載せる:

- collection → `object[]` + `child_entity`（従来どおり）
- singleton object → wrapper + ドット名エッジ（エンティティ内と同じ吸収規約）
- scalar / scalar array → 通常の属性（`child_entity` なし）
- `__definition` も `__root` の属性として正規化される

波及として決める点:

- `__entity_defs` / `__data` / `__entity_tree` は `__definition.entities` を filter する view なので、`__root` レコードの表示方針（除外か、index の情報源への昇格か）
- `from:` が singleton を指した場合のエラーを「unknown source」から「collection ではない」に改善できる
- `check_xref_coherence` の `parent_entity is None` フィルタから `__root` を除外

依存: E14 とは独立に着手できる（ルート singleton の吸収は既に「ドット = 入れ子」の規約に乗っている）。J5 は両方を前提とする。

[E17 (合成ビュー)](../60-composer/10-query-dsl-spec.md#合成ビュー-e17) はトップレベル・シングルトンのカタログ表現を前提にするので、M13 は E17 の前段でもある。合成ビューを `__root` の属性として吸収するか、view 同様に独立の項目として emit するかは E17 側で決める。

### singleton 平坦化の 1 段制限の撤廃 (M14)

`schema_tree._collect_edges` は singleton（record 形）を親エンティティの属性としてインライン化するが、**1 段だけ**である。singleton の下にさらに singleton があると、孫はカタログに現れない。配列が挟まると `to_catalog_node` で再帰が入り直すため平坦化の予算がリセットされる、という非対称もある（`テーブル.列[].参照.テーブル` は出るが `画面.メタ.責任者.名前` は出ない）。

実測（`画面` 直下に `メタ.責任者.{名前, 履歴[]}` を置いたスキーマ）:

```
現行:   画面 の attributes = [id, メタ(object), メタ.責任者(object)]        ← ここで打ち切り
        entities = [画面]

再帰化: 画面 の attributes = [id, メタ, メタ.責任者, メタ.責任者.名前,
                             メタ.責任者.履歴(object[])]
        entities = [画面, 画面.メタ.責任者.履歴]
```

実害は三つ:

- **読み側の DSL が届かない**: `select: - item: メタ.責任者.名前` は、データに値があってもエッジが無いので `unknown attribute` で落ちる。`where` / `sort` / `join.on` も同じ
- **深い collection が walk できない**: `from: 画面.メタ.責任者.履歴` に到達できない。E10 が深さ 1 で達成した walkability が深さ 2 で切れている
- **カタログから JSON の形が復元できない**: `メタ.責任者` は「type=object・子エッジ無し」としか言えず、*空オブジェクト* なのか *中身をカタログが知らない* のか区別できない。E14 がドットの**解釈**の曖昧さを消しても、この**情報の欠落**は別口で残り、J5 が塞がったままになる

**案**: `_collect_edges` の singleton 分岐を再帰化し、任意の深さの singleton をドット名エッジとしてインライン化する。

#### 背景: 「entity の濫造」は何を指していたか

制限は E10 (#196) が導入したものではなく、E10 が「今回は変えない」と線を引いた既存挙動である。E10 のコミット本文は *"Scalar and nested-singleton sub-properties **continue to** flatten as opaque attributes — deep nested-object structure is intentionally not extended into the catalog, to keep entity proliferation under control"* と書く。[schema-spec.md](../50-normalizer/20-schema-spec.md) の対応する一文も同じ PR で、隣接する「シングルトンは entity 化されない」という文の末尾に追記されたものである。つまり「entity の濫造」という語彙は隣の文（singleton を entity にするか否か）から借りたもので、孫エッジを出すか否かという論点には元々かかっていない。

再帰化して実際に増えるものを計測すると:

- スカラの孫 → ドット名の属性が増えるだけ。`Node.is_entity` は「子を持つか」なので entity は増えない
- **singleton の 2 段以上下にある配列 → entity が 1 件増える**。これが「濫造」の実体
- showcase 4 本と dev-docs では増減ゼロ（singleton 配下に singleton を置いた例が無い）

そして増える唯一の entity は、E10 がまさに「`from: <singleton>.<collection>` で walk できる first-class entity として見せる」と意図的に可視化したのと同種のものである。深さ 1 で見せる価値があると判断したものを深さ 2 で隠す理由は残っていない。

再帰の停止は問題にならない。property 名は schema-schema が `^[\p{L}_][\p{L}\p{N}_]*$` で縛っていてドットを含めないので、どれだけ深くてもドット名の分解は一意である。

#### 波及

- entity と属性が**増える方向**の変化なので breaking ではないが、深い singleton を持つプロジェクトでは entity 一覧・ER 図・`entity_def.md` の出力が変わる
- `docs/reference/schema.md` の Single-record pattern の記述
- [schema-spec.md](../50-normalizer/20-schema-spec.md) の 1 段制限の記述を書き換える
- 確認事項: アンカーパス（[anchor-spec.md](../70-generator/20-anchor-spec.md) の「dict キー（singleton 配下のキー）」）と `data_tree` が、深くなったドット名で破綻しないか

**未決: フィクスチャをどうするか。** showcase 4 本のどれも singleton 配下に singleton を持たないため、再帰化しても差分ゼロで、実機確認の対象が存在しない。showcase に入れ子 singleton を足すか（見本として自然な構造になるかは要検討。構造のためだけに項目を足すのは避けたい）、単体テストのみで済ませるかは着手時に決める。

依存: E14 の前提。M13 とは独立に着手できる（M13 のルート吸収規約は「エンティティ内と同じ吸収規約」を参照しているので、M14 が先に入れば再帰版を自動的に継承する）。

### tap ドキュメントの JSON Schema 提供 (J5)

`mood tap` の data.json はテンプレートに流し込まれるルートオブジェクトそのものであり、その JSON Schema は tap 消費者（typegen・検証）とテンプレートを書く LLM の両方に効く。データからの探索と違い、レコード 0 件のエンティティ（キーごと消える）や absent な任意項目も語れる。

**案**: `components/shared/json_schema.py` に純関数を置く:

- `document_schema(entities) -> Mapping` — data.json 全体のスキーマ
- `entity_schema(entity_id, entities) -> Mapping` — 単一エンティティの断片（子孫を入れ子展開）

変換の要点: ドット名の入れ子復元（E14 で「カタログのドットは必ず入れ子」が保証される前提）、ルートの合成（M13 の `__root` 前提）、`[]` 接尾の再帰的な `items` への展開、`validation` / `metadata` キーの素通し移送。

提供口は未決（tap データ本体には混ぜない — インタフェース分離）。候補: `__db/` メタ面への埋め込み（entity_def.md / view_def.md / 全体スキーマページ）、`mood tap --schema`、MCP ツール。導線（docs / MCP ツール記述）とセットで初めて使われる点に注意。

その他の論点: レコード 0 件エンティティのキー欠落と required 方針、`additionalProperties: false` の採否。

**着手トリガー**（いずれかが発生するまで保留）: (a) エージェントが tap データやテンプレート執筆で実際につまずく事例が出る、(b) SBOM 等で外部 JSON との型突き合わせが必要になる、(c) 利用者からスキーマ / typegen の要望が来る。前提タスク: E14, M13。
