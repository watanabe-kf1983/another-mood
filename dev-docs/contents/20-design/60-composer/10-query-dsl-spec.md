# Query DSL Specification

## External Design

### 背景: 永続化形式とクエリモデルの分離

著者がネスト（コンポジション）で書いたデータを、別の軸で再グループ化したいというニーズは、データの利用が進むにつれて事後的に現れる。`flatten:` 句は、著者の永続化形式（ネスト）を変更せずに、Composer のクエリモデル上で intrinsic 配列を unwind してフラットなアクセスを可能にする。詳細は [json-data-model.md](../40-communication/10-json-data-model.md) の「背景: なぜ永続化形式をフラット化しないか」を参照。

### 背景: where の closed set から `neq` (not equal) を外した理由

DB DSL によくある `neq` を入れなかったのは、対象キーが欠落しているレコードで何を返すべきかが、自然な読み方で 3 通りに分かれるため:

- 実データ上の `≠` と読めば **True** (値がないので x とは異なる)
- SQL の 3 値論理として読めば **UNKNOWN** (NULL の neq は UNKNOWN なので False 寄り)
- 「`eq` の論理否定」と読めば **True** (`eq` が False なので flip して True)

`neq` を closed set に入れると、どの解釈を採っても残り 2 つを期待した利用者から不自然に見える。代わりに「atomic 述語は欠落キーで常に False」+「`not` は内側の結果を flip」の 2 規則で semantics を一意化し、「等しくない」が必要なら `not: { field: x }` と書く設計にした。否定の挙動が `not` 1 箇所に集約され、述語ごとに考えなくてよくなる。

### 背景: sort の keyword に `null` ではなく `missing` を採用した

ツールの data model は「nullable は項目自体を省略する」が原則で、独立した「null 値」概念を持たない ([json-data-model.md](../40-communication/10-json-data-model.md))。where 句も存在判定は `exists: true/false` で表現しており、`null` という語は DSL のどこにも出てこない。ここだけ SQL の `NULLS FIRST/LAST` を借用すると語彙が不揃いになる。`missing: first/last` は「missing key」をそのまま表現し、`exists` と語彙が並ぶ。ElasticSearch も `missing: _first/_last` を採用しており、JSON/YAML 上の DSL では先例がある。

### 背景: sort の `direction` × `missing` を直交にした上で default は direction 非依存にした

null/missing 位置の決め方は DB エンジン間で割れる。SQL 系は二派ある:

- direction 従属派 (MySQL, SQL Server, MongoDB, CouchDB 等): null を最大/最小値固定で扱い、`asc` / `desc` で位置が自動で決まる。明示パラメータを持たない
- 直交派 (PostgreSQL, Oracle, DuckDB, ElasticSearch, pandas): `NULLS FIRST/LAST` / `missing` / `na_position` を別パラメータで指定

本 DSL は後者を採る (前者なら `missing:` キーを設ける意味が薄い、かつ「null は値の一種」という SQL の前提が data model に合わない)。

直交派の中でもデフォルトはさらに分かれる:

- direction-dependent (PostgreSQL: `ASC NULLS LAST` / `DESC NULLS FIRST`、SQLite はその逆): 「null は最大値 (or 最小値)」という基底ルールから direction で導出される
- direction-independent (ElasticSearch, pandas: 常に `last`): direction 不問

本 DSL は後者を採る。「missing は末尾」が `asc` / `desc` どちらでも成り立つ不変条件で覚えられ、ユーザが「null は値として何位扱いか」を内面化する必要がない。

### 背景: `flatten:` 句を「intrinsic 配列専用」とした

`flatten:` (top-level 句) はデータの永続形式そのものである intrinsic な配列 (composition-child / scalar 配列 / FK 配列) のみを unwind 対象とする。後続 E3 で導入される `join:` の `as:` 由来配列は対象外で、そちらは `join[].flatten:` インライン側で扱う。

責任分離の理由: intrinsic 配列の unwind は「永続形式に対する読み方の表明」で、データの shape そのものに紐づく。一方 join 由来の配列は query が transient に作ったものなので、その shape の調整は join 句内で完結させた方が cause-fix locality が保てる。

### 背景: `flatten:` 後の row shape に namespace 保持を採用した

`flatten: { of: tasks, as: task }` の出力は `{ id, title, task: { ... } }` のように **親 fields を top-level に残し、 child を `as:` 名の namespace 配下に置く** 形にした。child の field を top-level に昇格させて親情報を捨てる方式は採らない。

利点:
- 親 fields は flatten 後の row top-level からそのまま読めるので、別 row への遡行機構を別途用意する必要がない
- 複数 flatten / join の重ね合わせでも namespace で衝突回避できる
- `as:` の意味が (E3 で導入される) nested join (= 配列名) と flat 化後 (= scalar 名) で完全に一致する (どちらも namespace prefix)

### 背景: 走査の非対称性を設計原則として確立した

**`flatten:` 系の句以外は、現 row の attribute (nested object 内の dot path を含む) のみを参照対象とし、 nested array の中身には潜らない**。配列に潜る (= cardinality を変える) 操作は `flatten:` (および E3 で導入される join 内 inline flatten) に集約し、 `where:` / `sort.by:` のような述語・selector 句側に array walk を持ち込まない。

| 句 | 現 row の attribute (nested object dot path 含む) | nested array の中身 |
|---|---|---|
| `where:` | ✅ 参照可 | ❌ 参照不可 |
| `sort.by:` | ✅ 参照可 | ❌ 参照不可 |
| `flatten:` | (操作対象は array attribute) | ✅ (展開のために潜る) |

E3 で `join.on:` がこの表に加わるが、 同じ原則 (array に潜らない) に従う。

この非対称性ルールにより:

- nested array に触りたいユーザは必ず `flatten:` 系を経由する → cardinality 変化を必ず明示することになる
- 「ここだけ特例で潜れる」asymmetry が発生せず、句の責任が明確
- 将来の DSL 拡張も「array 走査は別句で」が原則として残る

実装上はこの規則を catalog の木の探索が持つ。`Node.descend` は singleton の子 Node を降りるが `[]` エッジに当たるとそこで止まる — パスは配列属性で終われるが、その先へは続けない。`where` / `sort.by` / `join.on` はこの `descend` (`require_path`) を通すだけで array 跨ぎが弾かれる。`select` は wrapper edge を選んだときその子 Node ごと連れて行く挙動 (apply 側 `pluck` の挙動と整合) で、 singleton の sub-attribute をひとまとめに扱う。

### パイプライン順序

```
from
→ flatten          (intrinsic 配列の unwind、list 内項目順序)
→ join             (list 内項目順序、各 item は post-join に inline flatten 可)
→ where            (post-join filter)
→ grouped
→ select
→ sort
```

interleave (flatten → join → flatten → ...) は list 内項目順序で表現する。intrinsic 配列の「途中段」flatten はサポート外で、必要なら別ビューに分割する。

`sort` を `select` の後ろに置くのは、`sort.by:` が `select:` の `as:` で導入された出力名を参照できるようにするため。SQL の論理処理順序 (`SELECT` → `ORDER BY`)、MongoDB aggregation (`$project` → `$sort`)、PRQL (`select` → `sort`)、Pandas (`assign` → `sort_values`)、LINQ (`Select` → `OrderBy`) いずれも同じ慣例。

### 背景: ビュー間参照に名前付き参照を採り、インラインサブクエリを採らない

`from:` / `join.to:` のソース名には、データエンティティだけでなく他のビューも書ける（RDBMS の view を FROM 句に書く、Access の保存クエリを別クエリのソースにするのに相当）。builtin ビュー (`__builtin`) も同一名前空間で参照対象。動機は三つ:

- **パイプライン固定順序の逃し弁の実体化**: 本 DSL は句の順序を固定し、順序に収まらない形（途中段 flatten 等）への公式の答えは「別ビューに分割する」（「パイプライン順序」節）。だが分割した後段が前段を参照できないと、実際の回避策は共通前段の複製かテンプレート側での再結合になってしまう。名前付き参照はこの逃し弁を実体化する
- **共通前段の重複排除**: 複数ビューが同じ整形（flatten + join 等）を前段に持つとき、名前付きの中間ビューとして一度だけ書ける
- **DSL 成長圧のキャップ**: 「句 X を順序 Y にも置きたい」系の拡張要望への標準回答が「分割」になり、句・順序オプションの増殖を抑える。dbt が SQL（サブクエリを書ける言語）の上に「入れ子禁止・名前付きモデルの DAG 参照」の規約を敷いて収斂したのと同じ構図

**インラインサブクエリ**（`from:` にクエリオブジェクトをネストさせる、SQL のサブクエリ相当）は採らない:

- RDBMS 現場の「ビュー禁止」文化の根拠（オプティマイザの実行計画不透明性、ビュー重ね掛けの性能崖）は、ビルド時に全ビューを一度だけ決定的な順序で評価し結果を実体化する本ツールには存在しない。ここでのビュー参照は RDBMS の view より「スクリプト内の中間変数」に近い
- 入れ子の内側は本ツールで唯一「中間結果が実体化されない」場所になり、`view-results/` を読んで段ごとに確かめられる実体化デバッグの強みに穴を開ける
- YAML で再帰構造を書く人間工学は SQL の括弧より悪い
- 局所性が本当に効く場所には既に制限付きインライン（`join.to:` + `join.where:`）があり、全面開放の圧力はない
- 名前付き参照からインライン併用への拡張は純粋な追加（`from:` が名前 or クエリオブジェクトを取る schema 再帰化）なので、命名疲れの実例が積み上がってから再検討できる

**提示順は不変**: ビュー間参照は評価順（依存 → 依存元の topo 順）にのみ影響し、`__definition.views` の並びはファイル順のまま。評価の実装（依存グラフ・サイクル診断・derive 失敗のカスケード抑制）は [query.py](../../../../src/another_mood/components/shared/query.py) の `evaluation_order` と query_deriver の `_derive_all` の docstring を参照。

**受容済みの制約 — 名前空間汚染**: 中間段のためだけの補助ビューも、テンプレートから見え、メタドキュメンテーション（ER 図・ビューカタログ）に載る。当面は命名規約で凌ぎ、痛くなったら `internal: true` 等の可視性フラグを検討する。

### 背景: `join:` の inline flatten を採用した理由

flat 化したいときに「join が作った array を別句 `flatten:` で fix する」のは、shape 生成と shape 修正の責任が join と flatten に分散する。**cause = fix を同じ場所に置く** ため、flat 化を意図する join では item 内に `flatten:` を inline で書く。

旧案の `kind: nested | flat_inner | flat_left` enum も検討したが、(a) 動詞 (`flatten:`) を per-join 配置することで kind 名の暗記負担を減らし、(b) `preserve_empty` 等のオプションを naturally に乗せられる、(c) MongoDB の `$lookup` + `$unwind` のように nest と flat をファーストクラスで扱うエンジンの構造に近い、という利点がある。

### 背景: `grouped.as` を必須にした

別名スロット `as:` の省略可否は一本の規則で引く:

> `as:` は、ソースを同じマッピングに書く句（`flatten.of` / `join.to`）では省略可。書かない句（`grouped`）では必須。

`flatten` / `join` の `as` が省略できるのは、命名対象が同じマッピングの `of:` / `to:` の要素そのものだからで、その名前を既定値にしても意味が外れない。`grouped` が束ねるのはパイプラインを通過した行であって `from:` の行ではない。

### 背景: `select` は欠落キーを出力から省く

`select` の各 `item:` は、その attribute がレコードに存在しないとき (= schema 上 optional な属性で値が省略されているとき) は **出力レコードから当該キーを省く**。エラーにはしない。

理由は data model 全体での「nullable = キー省略」原則との整合 ([json-data-model.md](../40-communication/10-json-data-model.md))。`null` 値概念を持たない data model の下では、optional 属性が省略されたレコードは「キーがない」状態で素直に走るのが筋。`select` がここで `null` を捏造したりエラーで止めたりすると、後段の述語 (`where: { exists: false }`) や下流テンプレートの falsy 判定が壊れる。

具体例: `from: __definition.entities` に `select - item: parent_entity` を入れると、top-level entity (= `parent_entity` キーが無い) は `parent_entity` キーを持たない行を吐き、child entity (= `parent_entity` に親 id) は値付きの行を吐く。出力レコードの shape が記録ごとに揺れることになるが、これは下流での `if row.parent_entity` 判定で自然に消える。

この semantic は `from` / `flatten` / `where` / `grouped` といった他の DSL 句の missing-key 扱い (where 述語は欠落キーで常に False、sort は `missing: first/last` で位置を指定) と合わせて、「DSL は欠落を一級扱いする」運用に揃える。

### スコープ外: nested-list 操作

下記は本ツールではサポートしない。 追加シンタックスが必要で、当面実現予定はない:

- **ツリー shape 出力** (例: 各 category の tasks 配列内で phase を FK 引きして埋め込む)
- **nested array の中身に対する filter / sort** (例: tasks 配列の中身が特定条件を満たすかで category を絞る)

## Internal Design

### 背景: `Join` を `QueryNode` に乗せず特別扱いした理由

`join:` は 2 入力 1 出力で、他の op (`from` / `flatten` / `where` / `grouped` / `select` / `sort` はすべて 1-in 1-out) と arity が異なる。既存の `QueryNode` Protocol (1-in 1-out 想定) には乗らないので、`Join` を `QueryNode` 非該当のクラスとし、`Query.apply` / `Query.derive` 内で pipeline 順序を直書きする形で扱う。apply 側と derive 側で同じ順序を 2 度書き下すため ~10 行ずつ重複が生じるが、現スコープではこの局所的な特別扱いの方が抽象階層導入より軽い、と判断した。

検討した代替案として、評価器を 3 層 (Query が pipeline 順序を独占し、Stage 層が汎用 wiring を担い、Op 層が純粋関数として arity ごとに分かれる) に分解する tree/pull 評価器が挙がる。Join は `BinaryOp` + `BinaryStage` の組として一貫性ある形で扱える。利点は (a) 1-input / 2-input が型レベルで対等に並ぶ、(b) apply / derive の重複コードが再帰呼び出しで自然に消える、(c) 将来 union や sub-query reference 等の追加 op に拡張しやすい、こと。

欠点として、新規プロトコル / クラスが計 6 個 (`Stage`, `UnaryOp`, `BinaryOp`, `Origin`, `UnaryStage`, `BinaryStage`)、公開 API (`Query.apply` / `derive` シグネチャ) の変更、既存テスト / 呼び出し側への波及が発生する。

現スコープでは 2-input op は `join:` 1 つで、union 等の追加予定もない (D 群 / F 系の隣接タスクで言及無し)。「機械的重複 ~20 行を消すために 80+ 行の抽象階層を投資する」のは現状ではコスト過大と判断。

将来、2-input op が増える / 多 join のパターンが想定外に複雑化する等の signal が出たら、その時点で tree/pull への refactor を検討する。Join がすでに特別扱いされているので、その特別扱いを抽象化する方向への escalation は incremental に行える。

## Proposals

### ドット名の意味論統一 (E14)

#### 問題

DSL の名前に現れるドットは、読み側と書き側で意味が違う。読み側（`from:` / `flatten.of:` / `join.on:` / `where` のキー / `sort.by:` / `select.item:` / `grouped.by:`）ではパスで、`hobby.level` は `hobby` の中の `level` を指す。一方、書き側（出力レコードのキー名を決める別名スロット）ではリテラル文字列で、`"hobby.level"` というドット入りのキーをそのまま作る。

データにドット入りキーを生む経路は view の別名スロットだけである。schema.yaml の `properties` 名は識別子パターンで縛られ、map パターンのキーは `id` の値になるので、`contents/` からは生まれない。内蔵の `__definition` もデータ上は入れ子である。

| スロット | 省略時 | ドット入りキーが生まれる例 |
|---|---|---|
| `select[].as` | `item` をそのまま | `item: hobby.level` → `{"hobby.level": "pro"}` |
| `flatten.as` | `of` をそのまま | `flatten: hobby.pets` → `{"hobby.pets": {...}}` |
| `join.as` | `to` をそのまま | `to: __definition.entities` → `{"__definition.entities": [...]}` |
| `join.flatten.as` | join の `as` をそのまま | 同上 |
| `grouped.by` | （別名の口が無い） | `by: hobby.level` → `{"hobby.level": "pro", members: [...]}` |
| `grouped.as` | （必須。E16 で省略不可になった） | `as: a.b` と書ける |

この非対称が生む実害:

- **テンプレートの式が view を通すと変わる**: 元エンティティでは `member.hobby.level` で届く値が、`select` を通した後は `row["hobby.level"]` か `pluck` フィルタでしか届かない（Jinja2 の `row.hobby` は undefined になる）
- **`pluck` に longest-first 照合が要る**: 同じ `hobby.level` という文字列が、レコードによってリテラルキーにも入れ子パスにもなりうるため、`json_data_model.pluck` はまずキー全体を試し、駄目なら末尾セグメントを削って降りる。データの形が一意でないことの代償
- **カタログから JSON の形が復元できない**: `Attribute.id` のドットが singleton 平坦化（入れ子）なのかリテラルキーなのか区別できず、`entity_def.md` は両者を同じ見た目で表示し、tap ドキュメントの JSON Schema 生成（J5）が塞がる
- **読み側のうち `flatten.of` だけがパスを受けない**: apply (`_unwind`) は `of` と同名のトップレベルキーしか除去しないので、`of: hobby.pets` を通すと元の配列が `hobby` 内に残ったまま新キーが足され、「配列エッジを置き換えた」と言うカタログとずれる。derive がドット入りの `of` を `unknown attribute` として弾くことでずれは塞いであるが、読み側の一句だけがパスを受けない状態になっている

#### 方針: DSL の名前は読みも書きもパス

書き側のドットも入れ子として解釈する。`select: - item: hobby.level` の出力は `{"hobby": {"level": "pro"}}`。MongoDB の projection（`{"hobby.level": 1}` が入れ子を保つ）、TOML の dotted key（`hobby.level = "pro"` はテーブル `hobby` の定義）と同じ意味論。

##### 不変条件

- **データのキーはドットを含まない**。`contents/` 由来はもとより、view 出力も含めて
- **直列化カタログの `Attribute.id` のドットは必ず入れ子を意味する**。`hobby.level` は `hobby`（type=object）の中の `level`。`[]` 接尾は配列、`child_entity` は再帰。したがってカタログだけから JSON の形が一意に復元できる（ルートは M13 が前提）

##### カタログ出力の `required`

`required` の意味は変えない。JSON Schema と同じく、親のオブジェクトがあれば必ずあるという親に対する相対的な性質であり、「全行にある」という無条件の存在性ではない。書き込み先パスで合成されたオブジェクトとその子についても、derive はこの意味で正しい値を出す。

##### 空の object

中身の無い object は、レコードにもカタログにも残さない。書き込む値が無ければ途中のオブジェクトごと省き、除去で空になったオブジェクトは祖先まで遡って畳む。「nullable はキー省略」の原則の適用。

##### 重なりの判定（今後検討）

書き込み先がパスになると、二つの書き込みが同じ場所を取り合うかどうかは名前の一致では決まらない。どの組を重なりとして derive 段階でエラーにするかは未定で、別途検討する。

- `as: a` と `as: a.c` を、`a` がオブジェクトのとき衝突とみなすか（`jackson as j` と `brown.james as j.james`）
- 書き込みを葉に還元して判定するなら、オブジェクトの書き込みは常に合流になり、レコード側の書き込みも「置く」ではなく「合流させる」になる
- 中身が宣言されていないオブジェクトの扱い

#### 期待される振る舞い（代表例）

観点ごとに view の書き方と、レコード出力・カタログ出力の両方を示す。レコードは JSON、カタログは葉パス表記で書く。

葉パス表記の凡例: 葉ごとに、外側から `.` で繋いだパスを空白区切りで並べる。子を持つセグメントは object、持たないセグメントは string。エッジの性質は名前の後ろに付ける。`[]` は配列、`?` は任意（親があっても無いことがある）で、印の無いエッジは required。任意の配列は `pets[]?`。

##### 別名は入れ子に書く

```yaml
select:
  - { item: level, as: hobby.level }
# レコード: {"level": "pro"}  →  {"hobby": {"level": "pro"}}
# カタログ: level  →  hobby.level
```

##### 同じ親に書く複数の書き込みは合流する

子はレコードでもカタログでも書いた順に並ぶ:

```yaml
select:
  - { item: level, as: hobby.level }
  - { item: pets,  as: hobby.pets }
# レコード: {"level": "pro", "pets": 2, "extra": 1}  →  {"hobby": {"level": "pro", "pets": 2}}
# カタログ: level pets extra  →  hobby.level hobby.pets
```

##### 書く値が無ければ途中のオブジェクトも作らない

元の `level` が任意なら、`level` の無い行には `hobby` も無い。あれば必ず `level` を持つ:

```yaml
select:
  - { item: level, as: hobby.level }
# レコード: {"name": "Alice"}  →  {}
# カタログ: name level?  →  hobby?.level
```

##### `flatten` の `of` はパスで、配列は元の位置から除かれる

経路の途中のオブジェクトが無い行（`hobby` の無い行）は、配列が空の行と同じ扱い:

```yaml
flatten: { of: hobby.pets, as: pet }
# レコード: {"id": 1, "hobby": {"level": "pro", "pets": ["a", "b"]}}
#             →  {"id": 1, "hobby": {"level": "pro"}, "pet": "a"}
#                {"id": 1, "hobby": {"level": "pro"}, "pet": "b"}
# カタログ: id hobby.level hobby.pets[].name  →  id hobby.level pet.name
```

##### `flatten` の `as` もパスで、要素はその位置に入れ子で書かれる

```yaml
flatten: { of: hobby.pets, as: hobby.pet }
# レコード: {"id": 1, "hobby": {"level": "pro", "pets": ["a"]}}  →  {"id": 1, "hobby": {"level": "pro", "pet": "a"}}
# カタログ: id hobby.level hobby.pets[].name  →  id hobby.level hobby.pet.name
```

##### `of` と `as` の親が同じなら、その場で置き換わる

配列のあった位置に要素が入り、兄弟の並びは変わらない。親の object が持つもの（メタデータ・validation）もそのまま残る:

```yaml
flatten: hobby.pets
# レコード: {"id": 1, "hobby": {"pets": ["a", "b"]}}
#             →  {"id": 1, "hobby": {"pets": "a"}}
#                {"id": 1, "hobby": {"pets": "b"}}
# カタログ: id hobby.pets[]  →  id hobby.pets
```

```yaml
flatten: { of: tasks, as: task }
# レコード: {"a": 1, "tasks": ["x", "y"], "z": 2}
#             →  {"a": 1, "task": "x", "z": 2}
#                {"a": 1, "task": "y", "z": 2}
# カタログ: a tasks[] z  →  a task z
```

##### 除去で空になったオブジェクトは落ちる

```yaml
flatten: { of: hobby.pets, as: pet }
# レコード: {"id": 1, "hobby": {"pets": ["a"]}}  →  {"id": 1, "pet": "a"}
# カタログ: hobby.pets[].name  →  pet.name
```

##### `required` は親に対する相対的な性質として導く

任意の親を通して読んだ値は、外に書けば任意になる:

```yaml
select:
  - { item: hobby.level, as: level }
# カタログ: hobby?.level  →  level?
```

| 元 | `select` | 結果 | 読み |
|---|---|---|---|
| `a?.p a?.b.c` | `a.p as a.p`, `a.b.c as a.d` | `a?.p a?.d` | `a` があれば `b`, `c` があるので、`d` も `a` があれば必ずある |
| `a?.p a?.b?.c` | 同上 | `a?.p a?.d?` | `b` が任意なので、`d` は `a` があっても無いことがある |
| `a?.p x?` | `a.p as a.p`, `x as a.d` | `a?.p? a?.d?` | `x` はあるが `a` は無い行に `a: {d}` ができるので、`p` は `a` があっても無いことがある |
| `ref?.table ref?.column` | `ref.table as target.table`, `ref.column as target.column` | `target?.table target?.column` | 二つは同じ `ref` から来るので、`target` があれば両方ある |

`flatten` は行に何も足さない。`preserve_empty: false` なら要素の無い行が落ちるので `of` の経路は残った行の全部にあり、`true` なら元のまま:

| 元 | `flatten` | 結果 |
|---|---|---|
| `hobby?.level hobby?.pets[]` | `{ of: hobby.pets, as: hobby.pet }` | `hobby.level hobby.pet` |
| `hobby?.level hobby?.pets[]` | `{ of: hobby.pets, as: pet }` | `hobby.level pet` |
| `hobby?.level hobby?.pets[]` | `{ of: hobby.pets, as: hobby.pet, preserve_empty: true }` | `hobby?.level hobby?.pet?` |
| `hobby?.level hobby?.pets[]` | `{ of: hobby.pets, as: pet, preserve_empty: true }` | `hobby?.level pet?` |

##### `grouped.by` はキー値を `by` のパスの位置に書く

別名の口は無い:

```yaml
grouped: { by: hobby.level, as: members }
# レコード: {"id": 1, "hobby": {"level": "pro"}}
#           {"id": 2, "hobby": {"level": "pro"}}
#             →  {"hobby": {"level": "pro"}, "members": [{"id": 1, "hobby": {"level": "pro"}}, {"id": 2, "hobby": {"level": "pro"}}]}
# カタログ: id hobby.level  →  hobby.level members[].id members[].hobby.level
```

### 合成ビュー (E17)

#### 問題

「複数の entity / view を束ねた一つのページ」(文書) は、現状 root テンプレート (`index.md`) でしか組めない。サブテンプレートの束縛は主題だけ (paging-spec の「束縛の単一規則」) で、`render` の主題は `this` の子孫に限られるため、一つのプロジェクトから複数の文書を別ページとして出す手段が無い。`{% include %}` は root の文脈を共有するので `index.md` の肥大化は分割できるが、ページは作らない (showcase/system-dev-docs-ja の二文書 (S8) で表面化)。

代替案を検討して退けた:

- **edition 別ルートテンプレート**: edition は同一 report の体裁違いの概念で、文書の器に使うのは目的外利用
- **予約名 (`root` 等) でデータルートをサブテンプレートに渡す**: 主題以外に触る第二の入口になる。さらに、リンク解決は pre-render で静的に決まる (`page_path` はデータ位置と `file_per` だけから計算する) ので、文書ページに描いた既存ノードへのリンクは実際に描かれたページではなく `index.md` を指す。**文書はデータ位置を持つノードでなければならない**
- **`from: __root` のクエリ**: `select` 必須、単一レコード出力、使える句の制限、依存を `select` の鍵に限定、と特例が積み重なり、DSL の中に別物が同居する

#### 案: source を束ねる第二の view 文法

ビューの第二の文法として **合成 (`compose`)** を足す。views ディレクトリに書き、名前空間と評価順は query と共有する。ツール上の位置づけは generator の新機能ではなく **view の新機能**: データ木に名前付きのノードを一つ作るだけで、generator は何も知らない。

```yaml
# definition/views/文書.yaml
要求仕様書:
  compose:
    用語集: 用語                         # 葉 = source 名 (entity / view / 合成ビュー)
    要求:                                # 内側のマッピング = 入れ子のシングルトン (章)
      機能要求: 要求_by_ユースケース
      その他の要求: 要求_非機能
```

- **判別**: `from:` を持つものが query、`compose:` を持つものが合成 (view-schema の oneOf)。一つのファイルに混在できる
- **出力**: 単一レコード (object)。葉には source の**コピー**が入る。型 ID はデータ木の位置からそのまま出る (`要求仕様書` / `要求仕様書.要求` / `要求仕様書.用語集.item[]`)。アンカーパスは `/要求仕様書/用語集/書籍`
- **章節項**: 入れ子のマッピングがそのまま章になる。文法の追加は無く、`file_per: [要求仕様書.要求]` で章ページに割れる
- **評価順**: `source_names()` = 葉の集合。既存の `evaluation_order` に乗り、循環は既存の診断 (`query reference cycle`) に落ちる。合成が合成を葉に取ることも許す
- **query からは読めない**: 合成ビューは collection ではないので `from:` / `join.to` に指定できない (M13 の「collection ではない」診断)
- **テンプレート**: root で `{{ 要求仕様書 | render("要求仕様書.md") }}`。サブテンプレートは主題のフィールドが spread されるので `用語集` を素の名前で読める。文書横断参照はコピー経由 (`node("要求仕様書", "用語集", id)`)。元ノード (`/用語/書籍`) はどこにも描かれない。この作法は docs に明記する
- **カタログ**: 合成ビューはトップレベルのシングルトンで、`collect_entities` が落とす形 (M13 の穴)。`__view_defs` に shape を出し、コピーの型 ID → 元の型 (`type_index`。prose の見出しアンカーに要る) を引くために、トップレベル・シングルトンのカタログ表現が前提。**M13 が前提**。合成ビューを `__root` の属性として吸収するか、view 同様に独立の項目として emit するかは実装時に決める
- **句の名前は仮**。候補: `compose` / `bundle` / `sections`。query 句 (`from` / `flatten` / `join` / `where` / `grouped` / `select` / `sort`) との語感と、composer コンポーネント名との紛れを見て決める

#### 波及

- `view-schema.yaml`: 定義本体を query / compose の oneOf にする
- composer / query_deriver: 合成の derive (カタログ shape) と apply (コピー)。`_with_source` と同じ操作で root に吊る
- `docs/reference/view.md` に合成の節を追加。`docs/reference/template.md` の `render` に文書の例と文書横断参照の作法を追加
- 動機は S8 (showcase/system-dev-docs-ja)。S8 は暫定的に `index.md` の合本で進み、E17 後に文書の殻だけを合成ビューに移す
