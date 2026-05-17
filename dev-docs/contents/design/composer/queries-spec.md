# Queries Specification

## External Design

### 背景: 永続化形式とクエリモデルの分離

著者がネスト（コンポジション）で書いたデータを、別の軸で再グループ化したいというニーズは、データの利用が進むにつれて事後的に現れる。`flatten:` 句は、著者の永続化形式（ネスト）を変更せずに、Composer のクエリモデル上で intrinsic 配列を unwind してフラットなアクセスを可能にする。詳細は [json-data-model.md](../json-data-model.md) の「背景: なぜ永続化形式をフラット化しないか」を参照。

### 背景: where の closed set から `neq` (not equal) を外した理由

DB DSL によくある `neq` を入れなかったのは、対象キーが欠落しているレコードで何を返すべきかが、自然な読み方で 3 通りに分かれるため:

- 実データ上の `≠` と読めば **True** (値がないので x とは異なる)
- SQL の 3 値論理として読めば **UNKNOWN** (NULL の neq は UNKNOWN なので False 寄り)
- 「`eq` の論理否定」と読めば **True** (`eq` が False なので flip して True)

`neq` を closed set に入れると、どの解釈を採っても残り 2 つを期待した利用者から不自然に見える。代わりに「atomic 述語は欠落キーで常に False」+「`not` は内側の結果を flip」の 2 規則で semantics を一意化し、「等しくない」が必要なら `not: { field: x }` と書く設計にした。否定の挙動が `not` 1 箇所に集約され、述語ごとに考えなくてよくなる。

### 背景: sort の keyword に `null` ではなく `missing` を採用した

ツールの data model は「nullable は項目自体を省略する」が原則で、独立した「null 値」概念を持たない ([json-data-model.md](../json-data-model.md))。where 句も存在判定は `exists: true/false` で表現しており、`null` という語は DSL のどこにも出てこない。ここだけ SQL の `NULLS FIRST/LAST` を借用すると語彙が不揃いになる。`missing: first/last` は「missing key」をそのまま表現し、`exists` と語彙が並ぶ。ElasticSearch も `missing: _first/_last` を採用しており、JSON/YAML 上の DSL では先例がある。

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
- 親情報への独立アクセス経路 (`_parent` 等) を別途用意しなくてよい — M1 (`_parent` 補完) の必要性が薄まる
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

## Proposals

### 同名禁止 (E6)

クエリ名と正規化済みデータ名（テーブル名）の重複を禁止する（エラー）。クエリの `from:` は常に正規化済みデータ（テーブル）を指すため、同名を許すと循環参照が生じる。加工が必要な場合はクエリに別名を付ける。

> 現状は Composer が正規化済みデータと同名のクエリを silent に上書きする。Phase 10 タスク [E6](../../../tasks.md)。

### `join:` 句と `where:` 射程統一 (E3)

cross-table 結合と pre-/post-join filter の整理。`flatten:` 句と走査の非対称性 (External Design 節) の上に乗る。Phase 10 タスク [E3〜E4](../../../tasks.md)（仕様詰めが先）。

#### `join:` 句

cross-table 結合。1 query につき **0..N 個** の join 操作を持てる。複数なら list 形、1 つだけのときは list 省略の object 形でも書ける (`flatten:` と同様)。デフォルトでは右側を **`as:` 名 (省略時は `to:` と同じ) の nested array として左 row に attach** する。フラット展開が必要なら item 内で `flatten:` オプションを指定する。

```yaml
# nested: 1 row per cat、tasks は配列のまま残る (`as:` 省略でデフォルト = `to:` の "tasks")
from: cats
join:
  - to: tasks
    on: { left: id, right: cat }

# 同じ nested を object 形で書く (1 join のみなら list 省略可)
from: cats
join: { to: tasks, on: { left: id, right: cat } }

# inline flatten + singular rename: 1 row per (cat, task)、子のない cat は消える
from: cats
join:
  - to: tasks
    on: { left: id, right: cat }
    flatten:
      as: task                     # post-flatten の attr 名

# inline flatten + preserve_empty: 子のない cat も残す (LEFT 相当)
from: cats
join:
  - to: tasks
    on: { left: id, right: cat }
    flatten:
      as: task
      preserve_empty: true
```

`flatten:` の短縮形 `flatten: true` は「rename なし、`preserve_empty: false`」(= `flatten: {}`) と等価。短縮形では配列名 (plural) のまま単一値が入るため、英語環境では `flatten: { as: task }` のように singular へ rename することが多い。日本語名のように単複で形が変わらない場合は短縮形で十分。

- **`to:`** (必須) — right 側 entity の ID
- **`on:`** (必須) — `{ left: <attr>, right: <attr> }` の単一キー eq のみ。複合キー / 非 eq 比較 (gt / like 等) / FK 自動推論はスコープ外。`left:` および `right:` は **現 row および right entity の attribute (nested object 内の dot path 含む、array は不可)** のみを参照対象とする (走査の非対称性ルールに従う)
- **`as:`** (optional、デフォルト = `to:` の値) — nested 段の namespace 名。衝突 (左側 attribute と同名、同 entity への複数 join 等) を避けたいときに上書き。post-flatten 名は `flatten.as:` 側で指定する
- **`where:`** (optional) — right 側 relation の pre-join filter。top-level `where:` と同じ predicate 構文で、pre-/post- は位置で区別する。3 つの cardinality 形態すべてで使える。**特に inline flatten + `preserve_empty: true` (= flat_left 相当) で右側 row を絞りたい場合は必ずこの `join[].where:` を使うこと** — top-level `where:` (post-join) に書くと事実上 INNER に劣化する SQL の有名な罠と同じ事象が起きる
- **`flatten:`** (optional) — 後段で `as:` の配列を unwind する
  - 短縮形 `flatten: true` で「rename なし、`preserve_empty: false`」
  - object 形では `as:` (optional、デフォルト = join の `as:`) で post-flatten 名を rename、`preserve_empty:` (optional、デフォルト `false`、top-level `flatten:` と同義) で空配列の親を残すか指定

アクセスは `row.<final-as>.<field>` の形 (nested では `row.<as>` が配列、inline flatten 後では単一 object)。`<final-as>` は `flatten.as:` が指定されていればそれ、なければ join の `as:` (デフォルトでは `to:`)。

##### 多 join

list 内は順序評価。後段の `on.left:` は前段が `flatten.as:` (省略時は join の `as:`) で導入した attribute を **scalar として** 参照できる (前段が flatten 済みの場合):

```yaml
from: orders
join:
  - to: customers
    on: { left: customer_id, right: id }
    flatten:
      as: customer                                  # post-flatten 名
  - to: addresses
    on: { left: customer.address_id, right: id }   # customer は前段で flatten 済み
    flatten:
      as: address
```

前段が nested (flatten なし) の場合、その結果は array なので、後段の `on.left:` で配列名を scalar として参照することはできない (走査の非対称性ルール)。

##### スコープ外

- `on:` の複合キー、非 eq 比較
- FK 自動推論 (`on:` 省略)
- nested-list 走査 (詳細は後述「スコープ外: nested-list 操作」)

##### 背景: inline flatten を採用した理由

flat 化したいときに「join が作った array を別句 `flatten:` で fix する」のは、shape 生成と shape 修正の責任が join と flatten に分散する。**cause = fix を同じ場所に置く** ため、flat 化を意図する join では item 内に `flatten:` を inline で書く。

旧案の `kind: nested | flat_inner | flat_left` enum も検討したが、(a) 動詞 (`flatten:`) を per-join 配置することで kind 名の暗記負担を減らし、(b) `preserve_empty` 等のオプションを naturally に乗せられる、(c) MongoDB の `$lookup` + `$unwind` のように nest と flat をファーストクラスで扱うエンジンの構造に近い、という利点がある。

##### 背景: 単一 eq / FK 自動推論を入れない理由

ORM 風の FK 自動推論を入れない方針は queries-spec の他の決定 (`where:` の neq 除外など) と同系統で、「狭く明示的に置く」原則による。FK 制約が D 群で正式に schema に入った後も、`on:` 省略可能化方向には進めない。

##### 背景: `where:` 共通化 (旧案 `filter:` 不採用)

pre-join filter にも top-level と同じ `where:` キーを使う。同じ構造の predicate に別名 (旧案では `filter:`) を与えると認知負荷が増えるため、pre-/post- の区別は位置に委ねる。MongoDB の `$lookup.pipeline` 内で top-level と同じ `$match` を使う構造と同種の整理。

#### パイプライン順序 (E3 完了後)

```
from
→ top-level flatten          (intrinsic 配列の unwind)
→ join                       (list 順、各 item は post-join に inline flatten 可)
→ where                      (post-join filter)
→ grouped
→ select
→ sort
```

interleave (flatten → join → flatten → ...) は list 内項目順序で表現する。intrinsic 配列の「途中段」flatten はサポート外で、必要なら別 query に分割する。

`sort` を `select` の後ろに置くのは、`sort.by:` が `select:` の `as:` で導入された出力名を参照できるようにするため。SQL の論理処理順序 (`SELECT` → `ORDER BY`)、MongoDB aggregation (`$project` → `$sort`)、PRQL (`select` → `sort`)、Pandas (`assign` → `sort_values`)、LINQ (`Select` → `OrderBy`) いずれも同じ慣例。

#### 評価器の構造

`join:` は **2 入力 1 出力** の操作で、他の op (`from`, `flatten`, `where`, `grouped`, `select`, `sort` はすべて 1-in 1-out) と arity が異なる。既存の `QueryNode` Protocol (1-in 1-out 想定) には乗らないため、E3 では Join を `QueryNode` 非該当のクラスとして別途定義し、`Query.apply` / `Query.derive` で直書きの特別扱いを挟む方針を採る。

- `Join` クラスは `QueryNode` を継承しない。merge ロジックを純粋な 2-input 関数 (`merge_records(left, right)` / `merge_catalog(left, right)`) として持つ
- `Join` の右側 (右 entity + 任意の pre-join `where:`) は再帰的に組み立てたサブ `Query` として保持する
- `Query` に `joins: Sequence[Join]` フィールドを追加。`Query.apply` / `Query.derive` は pipeline 順序を機械的に展開する中で joins を扱う
- apply 側と derive 側で同じ pipeline 順序を機械的に書き下すことになり、~10 行ずつ程度の重複が生じるが、汎用 2-input 抽象化を導入するより局所的な特別扱いの方が、現スコープ (1 つの 2-input op) では適切と判断

##### 背景: 汎用 2-input 抽象化を採らなかった理由

検討した代替案として、評価器を 3 層 (Query が pipeline 順序を独占し、Stage 層が汎用 wiring を担い、Op 層が純粋関数として arity ごとに分かれる) に分解する tree/pull 評価器が挙がる。Join は `BinaryOp` + `BinaryStage` の組として一貫性ある形で扱える。利点は (a) 1-input / 2-input が型レベルで対等に並ぶ、(b) apply / derive の重複コードが再帰呼び出しで自然に消える、(c) 将来 union や sub-query reference 等の追加 op に拡張しやすい、こと。

欠点として、新規プロトコル / クラスが計 6 個 (`Stage`, `UnaryOp`, `BinaryOp`, `Origin`, `UnaryStage`, `BinaryStage`)、公開 API (`Query.apply` / `derive` シグネチャ) の変更、既存テスト / 呼び出し側への波及が発生する。

現スコープでは 2-input op は `join:` 1 つで、union 等の追加予定もない (D 群 / F 系の隣接タスクで言及無し)。「機械的重複 ~20 行を消すために 80+ 行の抽象階層を投資する」のは現状ではコスト過大と判断。

将来、2-input op が増える / 多 join のパターンが想定外に複雑化する等の signal が出たら、その時点で tree/pull への refactor を検討する。Join がすでに特別扱いされているので、その特別扱いを抽象化する方向への escalation は incremental に行える。

#### スコープ外: nested-list 操作

下記は本 E3 ではサポートしない:

- **ツリー shape 出力** (例: 各 category の tasks 配列内で phase を FK 引きして埋め込む)
- **nested array の中身に対する filter / sort** (例: tasks 配列の中身が特定条件を満たすかで category を絞る)

これらは追加シンタックスが必要であり、現時点では実現方式を確定しない。実現方式の候補としては Power Query M 風 (scope: キーや sub-pipeline)、サブクエリ参照 (`join.to:` に query 名を許す)、FK navigation 系の expand 構文等がある。D 群 (参照整合性) の進捗・実際のユースケース要請を見てから判断する。

### `_parent` 親参照 (M1)

ルート以外の全オブジェクトに親オブジェクトへの参照 `_parent` を付与する。 仕様は [json-data-model.md](../json-data-model.md#親参照-_parent-m1)。 Phase 11 タスク [M1](../../../tasks.md)。

`flatten:` の namespace 保持により「子 entity を unwind した row から親 fields を参照する」ユースケースは flat 化後の row top-level でカバーされる。 M1 が残カバーする領域は「flatten を介さない局面 (例: ネスト object 内からの一段外側参照)」に絞られる。
