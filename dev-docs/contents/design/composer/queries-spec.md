# Queries Specification

## External Design

### 背景: 永続化形式とクエリモデルの分離

著者がネスト（コンポジション）で書いたデータを、別の軸で再グループ化したいというニーズは、データの利用が進むにつれて事後的に現れる。`from` のドット記法は、著者の永続化形式（ネスト）を変更せずに、Composer のクエリモデル上でフラットなアクセスを可能にする。詳細は [json-data-model.md](../json-data-model.md) の「背景: なぜ永続化形式をフラット化しないか」を参照。

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

## Proposals

### 同名禁止 (E6)

クエリ名と正規化済みデータ名（テーブル名）の重複を禁止する（エラー）。クエリの `from:` は常に正規化済みデータ（テーブル）を指すため、同名を許すと循環参照が生じる。加工が必要な場合はクエリに別名を付ける。

> 現状は Composer が正規化済みデータと同名のクエリを silent に上書きする。Phase 10 タスク [E6](../../../tasks.md)。

### `flatten:` 句と `from:` 厳密化 (E11)

E1 (where) / E2 (sort) に続く DSL 拡充の前半。intrinsic 配列の unwind を行う `flatten:` 句を新設し、`from:` のドット記法を廃止する。後続の E3 (`join:` 導入) の前提となる「走査の非対称性」原則をここで確立する。Phase 10 タスク [E11](../../../tasks.md)。

#### `from:` 厳密 entity ID lookup

`from:` の値は catalog の entity ID と完全一致で解釈する。ドットを path separator として扱わない (entity ID の中にドットが含まれていてもよい)。

```yaml
from: members                # OK
from: __definition.entities  # OK (1 つの entity ID)
from: categories.tasks       # ❌ そのような entity は存在しないためエラー
```

E8 で導入した longest-match walk は、composition walk を `flatten:` 句に分離することで不要になる。`From.derive` は `catalog.child(name)` 単発 lookup に簡略化される (`walk_path` は sort field path 等で引き続き使用)。

##### 移行

`from:` のドット記法は dev-docs / showcase / built-in resources を通じて 4 箇所で使われている:

- `dev-docs/definition/queries/tasks-by-phase.yaml` — `from: categories.tasks` (真の composition walk)
- `src/another_mood/resources/queries/__entity_roots.yaml` — `from: __definition.entities` (単一 entity ID、`.` は ID 内の文字)
- `src/another_mood/resources/queries/__user_entity_roots.yaml` — 同上
- `src/another_mood/resources/queries/__user_queries.yaml` — `from: __definition.queries` (同様)

後者 3 件は entity ID として直接解決できる (path walk 不要) ため、実質的な書き換えは `tasks-by-phase.yaml` 1 件の `from: categories.tasks` → `from: categories` + `flatten: tasks` のみ。

##### 背景: `from:` から walk_path を切り離す

E8 (longest-match `walk_path`) は「同じ `a.b` 構文が entity ID と composition walk の両方を意味する」`from:` のための ambiguity 解消装置だった。本 E11 で composition walk を `flatten:` 句に分離するため、**`from:` 自体は walk_path を使わず単発 lookup に簡略化**できる。

ただし `walk_path` 本体は **他の句 (`sort.by:` 等) で nested object (singleton) 内の dot path 解決のため引き続き使用** する。例えば `sort: { by: profile.name }` のように、配列ではない入れ子オブジェクトの属性には dot path でアクセスできる。境界は catalog 上で明示されている (singleton は親 entity の attribute として平坦化、array は child entity として独立 — E10 参照): walk_path は singleton 境界では止まらず traverse するが、array (= child entity 境界) では止まる。array の中身に潜るのは `flatten:` 系の句に限る (走査の非対称性ルール)。

#### `flatten:` 句 (top-level、intrinsic 配列専用)

intrinsic な nested array (composition-child / scalar 配列 / FK 配列) を unwind する。後続の E3 で導入される `join:` の `as:` 由来配列に対しては適用不可とし、そちらは `join[].flatten:` で扱う。1 query につき **0..N 個** の flatten 操作を持てる。

```yaml
# 単一 attr (scalar 短縮形): preserve_empty: false、as: は attr 名と同じ
from: categories
flatten: tasks                     # 1 row per task、結果の attr 名は tasks

# 単一 attr + options (object 形)
from: categories
flatten:
  attr: tasks
  as: task                         # 結果の attr 名を変える (省略時は attr と同じ)
  preserve_empty: true             # 子のない親も残す

# 複数 attr (list 形): 順序評価で sibling な intrinsic 配列を unwind
# scalar / object を混在させてよい
from: members
flatten:
  - hobbies                        # 1 row per hobby
  - { attr: pets, as: pet }        # さらに 1 row per (hobby, pet)
```

各 item の field:

- **`attr:`** (必須) — unwind 対象の intrinsic 配列 attribute 名
- **`as:`** (optional、デフォルト = `attr:` と同じ) — 結果 row における namespace 名。配列だった attribute が単一要素の namespace に変わるため、英語の plural → singular のように rename したい場合に上書きする。日本語名のように単複が形を変えない場合は省略で十分
- **`preserve_empty:`** (optional、デフォルト `false`) — 子のない親 row を残すか。`false` だと drop。MongoDB `$unwind.preserveNullAndEmptyArrays` や Polars `.explode()` など業界慣行と一致させる

list 形は順序評価。後段の flatten は前段が unwind した row 状態を見るが、現スコープでは「sibling な top-level array attribute を順に unwind する」用途に限定する (ネスト array — 例えば `flatten: tasks` 後の `tasks.subtasks` — を更に潜るのはスコープ外、必要なら別 query に切り分ける)。

`flatten:` 後の row shape は **child を `as:` 名の scalar namespace として top-level に保持**:

```
before: { id, title, tasks: [t1, t2, t3] }
after (as 省略):     { id, title, tasks: t1 }, { id, title, tasks: t2 }, { id, title, tasks: t3 }
after (as: task):    { id, title, task: t1 },  { id, title, task: t2 },  { id, title, task: t3 }
```

親 fields は top-level (`row.id`、`row.title`)、child fields は namespace 経由 (`row.tasks.foo` または `row.task.foo`) でアクセス。

##### 背景: 「intrinsic 配列専用」と限定する理由

`flatten:` と (E3 で導入される) `join[].flatten:` の責任分離。intrinsic 配列はデータの永続形式そのもので、unwind は「読み方の表明」になる。join 由来の配列は query が transient に作ったもので、その shape の調整は join 句内で完結させたほうが cause-fix locality が保てる。

##### 背景: row shape (namespace 保持) を選んだ理由

旧 `from: a.b` は child を top-level に昇格し、親情報は失われた (M1 で `_parent` 補完を提案するに至った)。新 `flatten:` は親情報を top-level に残し、child を namespace 配下に置く。これにより:

- 親情報への独立アクセス経路 (`_parent` 等) を別途用意しなくてよく、M1 の必要性が薄まる
- 複数 flatten / join の重ね合わせでも namespace で衝突回避できる
- `as:` の意味が (E3 の) nested join (= 配列名) と flat 化後 (= scalar 名) で完全に一致する (どちらも namespace prefix)

#### 走査の非対称性 (設計原則)

**`flatten:` 系の句以外は、現 row の attribute (nested object 内の dot path を含む) のみを参照対象とし、nested array の中身には潜らない**。配列に潜る (= cardinality を変える) 操作は本 E11 で導入する `flatten:` (および E3 で導入される join 内 inline flatten) に集約し、`where:` / `sort.by:` のような述語・selector 句側に array walk を持ち込まない。

非配列の入れ子オブジェクト (catalog 上で singleton として親 entity に平坦化されているもの) は dot path で素直に参照可能。例: `sort: { by: profile.name }`、`where: { profile.age: 30 }` (`profile` は singleton)。

| 句 | 現 row の attribute (nested object dot path 含む) | nested array の中身 |
|---|---|---|
| `where:` | ✅ 参照可 | ❌ 参照不可 |
| `sort.by:` | ✅ 参照可 | ❌ 参照不可 |
| `flatten:` | (操作対象は array attribute) | ✅ (展開のために潜る) |

E3 で `join.on:` がこの表に加わるが、同じ原則 (array に潜らない) に従う。

この非対称性ルールにより:

- nested array に触りたいユーザは必ず `flatten:` を経由する → cardinality 変化を必ず明示することになる
- 「ここだけ特例で潜れる」asymmetry が発生せず、句の責任が明確
- 将来の DSL 拡張も「array 走査は別句で」が原則として残る

### `join:` 句と `where:` 射程統一 (E3)

cross-table 結合と pre-/post-join filter の整理。**E11 (`flatten:` 句と `from:` 厳密化) の完了を前提**とする。Phase 10 タスク [E3〜E4](../../../tasks.md)（仕様詰めが先）。

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
- **`on:`** (必須) — `{ left: <attr>, right: <attr> }` の単一キー eq のみ。複合キー / 非 eq 比較 (gt / like 等) / FK 自動推論はスコープ外。`left:` および `right:` は **現 row および right entity の attribute (nested object 内の dot path 含む、array は不可)** のみを参照対象とする (E11 で確立した走査の非対称性ルールに従う)
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

ORM 風の FK 自動推論を入れない方針は queries-spec の他の決定 (`where:` の neq 除外、`from:` の厳密化) と同系統で、「狭く明示的に置く」原則による。FK 制約が D 群で正式に schema に入った後も、`on:` 省略可能化方向には進めない。

##### 背景: `where:` 共通化 (旧案 `filter:` 不採用)

pre-join filter にも top-level と同じ `where:` キーを使う。同じ構造の predicate に別名 (旧案では `filter:`) を与えると認知負荷が増えるため、pre-/post- の区別は位置に委ねる。MongoDB の `$lookup.pipeline` 内で top-level と同じ `$match` を使う構造と同種の整理。

#### パイプライン順序 (E11 + E3 完了後)

```
from
→ top-level flatten          (E11、intrinsic 配列の unwind)
→ join                       (list 順、各 item は post-join に inline flatten 可)
→ where                      (post-join filter)
→ grouped
→ sort
→ select
```

interleave (flatten → join → flatten → ...) は list 内項目順序で表現する。intrinsic 配列の「途中段」flatten はサポート外で、必要なら別 query に分割する。

#### スコープ外: nested-list 操作

下記は本 E3 ではサポートしない:

- **ツリー shape 出力** (例: 各 category の tasks 配列内で phase を FK 引きして埋め込む)
- **nested array の中身に対する filter / sort** (例: tasks 配列の中身が特定条件を満たすかで category を絞る)

これらは追加シンタックスが必要であり、現時点では実現方式を確定しない。実現方式の候補としては Power Query M 風 (scope: キーや sub-pipeline)、サブクエリ参照 (`join.to:` に query 名を許す)、FK navigation 系の expand 構文等がある。D 群 (参照整合性) の進捗・実際のユースケース要請を見てから判断する。

### `_parent` 親参照 (M1)

`from` のドット記法でフラット化された各オブジェクトに `_parent` を付与し、親オブジェクトにアクセス可能にする（[json-data-model.md](../json-data-model.md) 参照）。

例: タスクをフェーズ別にグループ化する際にカテゴリ名（親）を表示する。

```yaml
# queries/tasks-by-phase.yaml
tasks_by_phase:
  from: categories.tasks
  grouped:
    by: phase
  select:
    - item: phase
      as: id
    - item: phase
    - item: tasks
```

```jinja2
{# templates/tasks-by-phase.md #}
{% for group in tasks_by_phase %}
## Phase {{ group.phase }}
| ID | タスク | カテゴリ | 状態 |
|---|---|---|---|
{% for task in group.tasks -%}
| {{ task.id }} | {{ task.title }} | {{ task._parent.title }} | {{ "✅" if task.done else "-" }} |
{% endfor %}
{% endfor %}
```

> 現状は `_parent` の付与自体が未実装のため、`task._parent.title` は空文字としてレンダリングされる。Phase 10 タスク [M1](../../../tasks.md)。
