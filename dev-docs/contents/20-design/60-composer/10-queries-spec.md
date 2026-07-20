# Queries Specification

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

実装上は catalog の encoding (singleton sub-object は親 entity の dotted-name sibling attribute として平坦化、 array は child entity として独立) に乗っているため、 `where` / `sort.by` 側で `has_child` による direct edge lookup を行うだけで自然に array 跨ぎが弾かれる。 `select` は wrapper edge 選択時に dotted siblings も連れて行く挙動 (apply 側 `pluck` の挙動と整合) で、 singleton の sub-attribute をひとまとめに扱う。

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

interleave (flatten → join → flatten → ...) は list 内項目順序で表現する。intrinsic 配列の「途中段」flatten はサポート外で、必要なら別 query に分割する。

`sort` を `select` の後ろに置くのは、`sort.by:` が `select:` の `as:` で導入された出力名を参照できるようにするため。SQL の論理処理順序 (`SELECT` → `ORDER BY`)、MongoDB aggregation (`$project` → `$sort`)、PRQL (`select` → `sort`)、Pandas (`assign` → `sort_values`)、LINQ (`Select` → `OrderBy`) いずれも同じ慣例。

### 背景: クエリ間参照に名前付き参照を採り、インラインサブクエリを採らない

`from:` / `join.to:` のソース名には、データエンティティだけでなく他のクエリの view も書ける（RDBMS の view を FROM 句に書く、Access の保存クエリを別クエリのソースにするのに相当）。builtin クエリ (`__builtin`) も同一名前空間で参照対象。動機は三つ:

- **パイプライン固定順序の逃し弁の実体化**: 本 DSL は句の順序を固定し、順序に収まらない形（途中段 flatten 等）への公式の答えは「別 query に分割する」（「パイプライン順序」節）。だが分割した後段が前段を参照できないと、実際の回避策は共通前段の複製かテンプレート側での再結合になってしまう。名前付き参照はこの逃し弁を実体化する
- **共通前段の重複排除**: 複数ビューが同じ整形（flatten + join 等）を前段に持つとき、名前付きの中間クエリとして一度だけ書ける
- **DSL 成長圧のキャップ**: 「句 X を順序 Y にも置きたい」系の拡張要望への標準回答が「分割」になり、句・順序オプションの増殖を抑える。dbt が SQL（サブクエリを書ける言語）の上に「入れ子禁止・名前付きモデルの DAG 参照」の規約を敷いて収斂したのと同じ構図

**インラインサブクエリ**（`from:` にクエリオブジェクトをネストさせる、SQL のサブクエリ相当）は採らない:

- RDBMS 現場の「ビュー禁止」文化の根拠（オプティマイザの実行計画不透明性、ビュー重ね掛けの性能崖）は、ビルド時に全クエリを一度だけ決定的な順序で評価し結果を実体化する本ツールには存在しない。ここでのクエリ参照は RDBMS の view より「スクリプト内の中間変数」に近い
- 入れ子の内側は本ツールで唯一「中間結果が実体化されない」場所になり、`query-results/` を読んで段ごとに確かめられる実体化デバッグの強みに穴を開ける
- YAML で再帰構造を書く人間工学は SQL の括弧より悪い
- 局所性が本当に効く場所には既に制限付きインライン（`join.to:` + `join.where:`）があり、全面開放の圧力はない
- 名前付き参照からインライン併用への拡張は純粋な追加（`from:` が名前 or クエリオブジェクトを取る schema 再帰化）なので、命名疲れの実例が積み上がってから再検討できる

**提示順は不変**: クエリ間参照は評価順（依存 → 依存元の topo 順）にのみ影響し、`__definition.queries` の並びはファイル順のまま。評価の実装（依存グラフ・サイクル診断・derive 失敗のカスケード抑制）は [query.py](../../../../src/another_mood/components/shared/query.py) の `evaluation_order` と query_deriver の `_derive_all` の docstring を参照。

**受容済みの制約 — 名前空間汚染**: 中間段のためだけの補助クエリも、テンプレートから見え、メタドキュメンテーション（ER 図・クエリカタログ）に載る。当面は命名規約で凌ぎ、痛くなったら `internal: true` 等の可視性フラグを検討する。

### 背景: `join:` の inline flatten を採用した理由

flat 化したいときに「join が作った array を別句 `flatten:` で fix する」のは、shape 生成と shape 修正の責任が join と flatten に分散する。**cause = fix を同じ場所に置く** ため、flat 化を意図する join では item 内に `flatten:` を inline で書く。

旧案の `kind: nested | flat_inner | flat_left` enum も検討したが、(a) 動詞 (`flatten:`) を per-join 配置することで kind 名の暗記負担を減らし、(b) `preserve_empty` 等のオプションを naturally に乗せられる、(c) MongoDB の `$lookup` + `$unwind` のように nest と flat をファーストクラスで扱うエンジンの構造に近い、という利点がある。

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
