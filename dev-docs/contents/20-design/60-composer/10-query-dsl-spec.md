# Query DSL Specification

## External Design

ビューは、エンティティや他のビューから新しいレコードの集合を導く名前付きのクエリで、テンプレートからはエンティティと同じように読める。句は固定順のパイプラインとして評価し、入れ子のまま書かれたデータを別の軸で束ね直すのもこのパイプラインの中で行う（[データモデルの制約](../../10-concept/10-product.md#データモデル-規律を与えた-json-の木)）。句ごとの文法と挙動は `docs/reference/view.md` が正本。以下は、その背後にある判断。

- 句の順序は固定し、収まらない形は別ビューに分割して名前付き参照でつなぐ。インラインサブクエリは採らない（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#ビュー間参照に名前付き参照を採りインラインサブクエリを採らない理由)）。評価順は参照関係から決まり、定義の並び（`__definition.views`）は変えない。中間ビューがテンプレートとメタドキュメントに見える制約は受容する
- 行の数を変えるのは `flatten` 系だけ。ソースに元からある配列は top-level の `flatten:` が、join が作った配列は join 内の `flatten:` が開く（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#flatten-句を-intrinsic-配列専用とした理由)、[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#join-の-inline-flatten-を採用した理由)）
- flatten 後の行は親の属性を残し、要素を `as:` の名前の下に置く（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#flatten-後の-row-shape-に-namespace-保持を採用した理由)）
- `as:` はソースを同じマッピングに書く句（`flatten.of` / `join.to`）では省略可、書かない句（`grouped`）では必須（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#grouped-の-as-を必須にした理由)）
- 欠落キーは data model の「nullable = キー省略」（[json-data-model.md](../40-communication/10-json-data-model.md)）に揃える。`neq` を持たず否定は `not` に集約し（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#where-の-closed-set-から-neq-を外した理由)）、sort は `missing:` で位置を指定して `direction` と直交にする（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#sort-の-keyword-に-null-ではなく-missing-を採用した理由)、[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#sort-の-direction-と-missing-を直交にし既定を-direction-非依存にした理由)）
- `sort` を `select` の後ろに置く（[先例](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#sort-を-select-の後ろに置く先例)）
- DSL の名前は読みも書きもパスで、ドットは入れ子を意味する。別名スロット（`flatten.as` / `join.as` / `select.as` / `grouped.as`、および `grouped.by` の書き戻し先）と view 名にドットを書けば出力は入れ子になり、view 出力にドット入りキーは生まれない（view 名の場合は中間の object が立つ）。兄弟への書き込み（`a.b` と `a.c`）は一つの object に合流し、片方が他方の先頭部分になる書き込み（`a` と `a.c`）は重なりとしてエラーにする。MongoDB の projection と TOML の dotted key と同じ意味論

### スコープ外: nested-list 操作

下記は本ツールではサポートしない。 追加シンタックスが必要で、当面実現予定はない:

- **ツリー shape 出力** (例: 各 category の tasks 配列内で phase を FK 引きして埋め込む)
- **nested array の中身に対する filter / sort** (例: tasks 配列の中身が特定条件を満たすかで category を絞る)

## Internal Design

各句は、レコード変換（`apply`）とカタログ変換（`derive`）を同じ DSL 断片から対にして持ち、両者が同じパイプラインを通る。これにより、データを評価せずに出力の形（カタログ）が分かる。

`join:` だけは 2 入力 1 出力で、1 入力 1 出力の `QueryNode` には乗せない。`Query.apply` / `Query.derive` がパイプライン順序を直書きして呼び分けるため両者で同じ順序が重複するが、2 入力の句が `join:` 一つしかない現状では、この局所的な特別扱いのほうが抽象階層より軽い（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#join-を-querynode-に乗せず特別扱いした理由)）。
