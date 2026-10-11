# Query DSL Specification (appendix)

[Query DSL Specification](../../../20-design/60-composer/10-query-dsl-spec.md) の背景。

## sort を select の後ろに置く先例

SQL の論理処理順序 (`SELECT` → `ORDER BY`)、MongoDB aggregation (`$project` → `$sort`)、PRQL (`select` → `sort`)、Pandas (`assign` → `sort_values`)、LINQ (`Select` → `OrderBy`) いずれも同じ慣例。

## `flatten:` 句を intrinsic 配列専用とした理由

`flatten:` (top-level 句) はデータの永続形式そのものである intrinsic な配列 (composition-child / scalar 配列 / FK 配列) のみを unwind 対象とする。`join:` の `as:` 由来配列は対象外で、そちらは `join[].flatten:` インライン側で扱う。

責任分離の理由: intrinsic 配列の unwind は「永続形式に対する読み方の表明」で、データの shape そのものに紐づく。一方 join 由来の配列は query が transient に作ったものなので、その shape の調整は join 句内で完結させた方が cause-fix locality が保てる。

## `join:` の inline flatten を採用した理由

flat 化したいときに「join が作った array を別句 `flatten:` で fix する」のは、shape 生成と shape 修正の責任が join と flatten に分散する。**cause = fix を同じ場所に置く** ため、flat 化を意図する join では item 内に `flatten:` を inline で書く。

旧案の `kind: nested | flat_inner | flat_left` enum も検討したが、(a) 動詞 (`flatten:`) を per-join 配置することで kind 名の暗記負担を減らし、(b) `preserve_empty` 等のオプションを naturally に乗せられる、(c) MongoDB の `$lookup` + `$unwind` のように nest と flat をファーストクラスで扱うエンジンの構造に近い、という利点がある。

## `flatten:` 後の row shape に namespace 保持を採用した理由

`flatten: { of: tasks, as: task }` の出力は `{ id, title, task: { ... } }` のように **親 fields を top-level に残し、 child を `as:` 名の namespace 配下に置く** 形にした。child の field を top-level に昇格させて親情報を捨てる方式は採らない。

利点:
- 親 fields は flatten 後の row top-level からそのまま読めるので、別 row への遡行機構を別途用意する必要がない
- 複数 flatten / join の重ね合わせでも namespace で衝突回避できる
- `as:` の意味が nested join (= 配列名) と flat 化後 (= scalar 名) で完全に一致する (どちらも namespace prefix)

## grouped の `as` を必須にした理由

別名スロット `as:` の省略可否は一本の規則で引く:

> `as:` は、ソースを同じマッピングに書く句（`flatten.of` / `join.to`）では省略可。書かない句（`grouped`）では必須。

`flatten` / `join` の `as` が省略できるのは、命名対象が同じマッピングの `of:` / `to:` の要素そのものだからで、その名前を既定値にしても意味が外れない。`grouped` が束ねるのはパイプラインを通過した行であって `from:` の行ではない。

## where の closed set から `neq` を外した理由

DB DSL によくある `neq` を入れなかったのは、対象キーが欠落しているレコードで何を返すべきかが、自然な読み方で 3 通りに分かれるため:

- 実データ上の `≠` と読めば **True** (値がないので x とは異なる)
- SQL の 3 値論理として読めば **UNKNOWN** (NULL の neq は UNKNOWN なので False 寄り)
- 「`eq` の論理否定」と読めば **True** (`eq` が False なので flip して True)

`neq` を closed set に入れると、どの解釈を採っても残り 2 つを期待した利用者から不自然に見える。代わりに「atomic 述語は欠落キーで常に False (`exists` を除く)」+「`not` は内側の結果を flip」の 2 規則で semantics を一意化し、「等しくない」が必要なら `not: { field: x }` と書く設計にした。否定の挙動が `not` 1 箇所に集約され、述語ごとに考えなくてよくなる。

## sort の keyword に `null` ではなく `missing` を採用した理由

ツールの data model は「nullable は項目自体を省略する」が原則で、独立した「null 値」概念を持たない ([json-data-model.md](../../../20-design/40-communication/10-json-data-model.md))。where 句も存在判定は `exists: true/false` で表現しており、`null` という語は DSL のどこにも出てこない。ここだけ SQL の `NULLS FIRST/LAST` を借用すると語彙が不揃いになる。`missing: first/last` は「missing key」をそのまま表現し、`exists` と語彙が並ぶ。ElasticSearch も `missing: _first/_last` を採用しており、JSON/YAML 上の DSL では先例がある。

## sort の `direction` と `missing` を直交にし、既定を direction 非依存にした理由

null/missing 位置の決め方は DB エンジン間で割れる。SQL 系は二派ある:

- direction 従属派 (MySQL, SQL Server, MongoDB, CouchDB 等): null を最大/最小値固定で扱い、`asc` / `desc` で位置が自動で決まる。明示パラメータを持たない
- 直交派 (PostgreSQL, Oracle, DuckDB, ElasticSearch, pandas): `NULLS FIRST/LAST` / `missing` / `na_position` を別パラメータで指定

本 DSL は後者を採る (前者なら `missing:` キーを設ける意味が薄い、かつ「null は値の一種」という SQL の前提が data model に合わない)。

直交派の中でもデフォルトはさらに分かれる:

- direction-dependent (PostgreSQL: `ASC NULLS LAST` / `DESC NULLS FIRST`、SQLite はその逆): 「null は最大値 (or 最小値)」という基底ルールから direction で導出される
- direction-independent (ElasticSearch, pandas: 常に `last`): direction 不問

本 DSL は後者を採る。「missing は末尾」が `asc` / `desc` どちらでも成り立つ不変条件で覚えられ、ユーザが「null は値として何位扱いか」を内面化する必要がない。

## ビュー間参照に名前付き参照を採り、インラインサブクエリを採らない理由

`from:` / `join.to:` に他のビューを書けるのは、RDBMS の view を FROM 句に書く、Access の保存クエリを別クエリのソースにするのに相当する。動機は三つ:

- **パイプライン固定順序の逃し弁の実体化**: 本 DSL は句の順序を固定し、順序に収まらない形（途中段 flatten 等）への公式の答えは「別ビューに分割する」（「パイプライン順序」節）。だが分割した後段が前段を参照できないと、実際の回避策は共通前段の複製かテンプレート側での再結合になってしまう。名前付き参照はこの逃し弁を実体化する
- **共通前段の重複排除**: 複数ビューが同じ整形（flatten + join 等）を前段に持つとき、名前付きの中間ビューとして一度だけ書ける
- **DSL 成長圧のキャップ**: 「句 X を順序 Y にも置きたい」系の拡張要望への標準回答が「分割」になり、句・順序オプションの増殖を抑える。dbt が SQL（サブクエリを書ける言語）の上に「入れ子禁止・名前付きモデルの DAG 参照」の規約を敷いて収斂したのと同じ構図

**インラインサブクエリ**（`from:` にクエリオブジェクトをネストさせる、SQL のサブクエリ相当）は採らない:

- RDBMS 現場の「ビュー禁止」文化の根拠（オプティマイザの実行計画不透明性、ビュー重ね掛けの性能崖）は、ビルド時に全ビューを一度だけ決定的な順序で評価し結果を実体化する本ツールには存在しない。ここでのビュー参照は RDBMS の view より「スクリプト内の中間変数」に近い
- 入れ子の内側は本ツールで唯一「中間結果が実体化されない」場所になり、作業ディレクトリ (`MOOD_TMP_DIR` で固定したとき) の `view-results/` を読んで段ごとに確かめられる実体化デバッグの強みに穴を開ける
- YAML で再帰構造を書く人間工学は SQL の括弧より悪い
- 局所性が本当に効く場所には既に制限付きインライン（`join.to:` + `join.where:`）があり、全面開放の圧力はない
- 名前付き参照からインライン併用への拡張は純粋な追加（`from:` が名前 or クエリオブジェクトを取る schema 再帰化）なので、命名疲れの実例が積み上がってから再検討できる

## `Join` を `QueryNode` に乗せず特別扱いした理由

`join:` は 2 入力 1 出力で、他の句 (`from` / `flatten` / `where` / `grouped` / `select` / `sort`) はすべて 1 入力 1 出力。1-in 1-out 想定の `QueryNode` Protocol には乗らないので、`Join` は `QueryNode` 非該当のクラスとし、`Query.apply` / `Query.derive` がパイプライン順序を直書きして呼び分ける。apply 側と derive 側で同じ順序を二度書くため 10 行程度ずつ重複するが、2 入力の句が `join:` 一つしかない現状では、この局所的な特別扱いのほうが抽象階層より軽い。

代替案は、評価器を Query（順序）/ Stage（配線）/ Op（arity ごとの純粋関数）の 3 層に分解する tree/pull 評価器。1 入力と 2 入力が型レベルで対等に並び apply / derive の重複も消えるが、新規プロトコルとクラスが 6 個増え、`Query.apply` / `derive` のシグネチャも変わる。2 入力の句が増える、多段 join が想定外に複雑化する、といった兆候が出た時点で検討する。既に特別扱いになっている `Join` を抽象化する方向なので、段階的に移せる。
