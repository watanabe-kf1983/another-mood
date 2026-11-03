# View

`docs/reference/view.md` の契約の外で、意図して保つ振る舞い。本文に出るステージ名（`derive_queries`、`compose`、`generate`）は[内部構造のステージ表](../20-internal/20-pipeline.md#ステージ構成)のもの。

本文で使う語:

- **ビュー** — クエリで導いた名前付きのレコードの集合。テンプレートからはエンティティと同じ名前空間で読める（`docs/reference/template.md` の Template context）
- **行** — クエリの句から句へ渡るレコード一件
- **メタドキュメント** — スキーマとビューの定義からツールが自動で描く `__db/` のページ
- **句のパイプライン** — 一つのクエリの中で、句が固定順に行を受け渡す流れ。ステージの連なりを指す内部構造の [Pipeline](../20-internal/20-pipeline.md) とは別物
- **`__definition.views`** — ビュー定義の一覧。[データカタログ](../20-internal/30-communication/20-data-catalog.md)の自己記述の一部で、メタドキュメントはここからビューの一覧を描く

## 句のパイプライン

### 句の順序は固定し、収まらない形は別のビューに分けて名前で参照する

句は固定順で評価する（`docs/reference/view.md` の Evaluation order）。この順に収まらない形（`where` で絞ってから `flatten` したい、`grouped` の結果を `join` したい、など）は、前段を別のビューに切り出し、`from:` や `join.to:` にその名前を書いてつなぐ。

`from:` にクエリを入れ子で書くインラインサブクエリは採らない。理由:

- 名前付きビューの結果は一つずつファイルに書き出され（`compose` の出力の `view-results/`）、段ごとに確かめられる。入れ子の内側は、唯一「中間結果が実体化されない」場所になる
- 共通の前段（flatten と join の組など）を一度だけ書ける
- 「句 X を順序 Y にも置きたい」という要望への標準の答えが「分割」になり、句と順序オプションの増殖を抑えられる
- YAML で再帰構造を書く人間工学は SQL の括弧より悪い

ビルド時に全ビューを一度だけ決定的な順序で評価して結果を実体化するので、RDBMS でビューを重ねたときの実行計画の不透明さはここには無い。ビュー参照は RDBMS の view より、スクリプトの中間変数に近い。

評価順は参照関係から決まり、ファイルの並びに依らない。一方で `__definition.views` の並びは、ファイルのパス順とファイル内の並びのままにし、評価順を利用者に見せない。

分割した中間ビューも、他のビューと同じにテンプレートとメタドキュメントに見える。隠す仕組みは持たない。

固定順のうち `sort` を `select` の後ろに置く（`sort.by` は射影後の名前を指す）のは、SQL（`SELECT` → `ORDER BY`）、MongoDB aggregation、PRQL、pandas、LINQ が揃って採る順に合わせたもの。

テスト:

- 評価順: `tests/components/shared/test_query.py` の `TestEvaluationOrder`、`tests/components/composer/test_composer.py` の `TestCompose.test_query_reads_another_query_out_of_file_order`
- 定義の並び: `tests/components/preprocess/test_query_deriver.py` の `TestDeriveQueries.test_definition_order_is_file_order`（一ファイル内の並び。パス順は守るテストが無い）
- 中間ビューが見えること: 無い。隠す機能が無いことはテストで守れない
- `sort` の位置: `tests/components/shared/test_query.py` の `TestQueryPipeline.test_apply_sort_after_select`

### 元からある配列は top-level の `flatten:`、join が作った配列は join の中の `flatten:` で開く

top-level の `flatten:` が開くのは、ソースのレコードに元からある配列（入れ子のコレクション、スカラの配列）だけ。join が `as:` に付けた配列は top-level の対象にせず、その join の中に `flatten:` を書いて開く。

元からある配列を開くことは、データの永続形式に対する読み方の表明で、データの形に紐づく。join の配列はクエリが一時的に作った形で、その調整は作った句の中で完結させたほうが、原因と直しが同じ場所に並ぶ。

契約が「行の中の配列に届く句は flatten だけ」と定める背後にも同じ姿勢がある。配列に手を入れる動詞を flatten 一つに集め、他の句は一行の属性だけを見る。

だから、配列の中身で親を絞る、配列の中を並べ替える、といった形のために句は足さない。配列は flatten で行に開いてから `where` や `sort` を当て、必要なら `grouped` や join の既定形（一覧のまま付ける）で束ね直す。

テスト: `tests/components/shared/test_query.py` の `TestQueryPipeline.test_apply_join_after_flatten`（top-level の flatten は join の前に走る）と `TestJoin.test_apply_chains_right_then_merge_then_flatten`。

### flatten 後の行は、親の属性を残し、要素を `as:` の下に置く

要素の属性を行の最上位に昇格させて親の情報を捨てる形は採らない。

- 親の属性が行からそのまま読めるので、親の行へ遡る機構が要らない
- flatten と join を重ねても、名前空間で衝突を避けられる
- `as:` の意味が、join の既定形（配列の名前）でも flatten 後（一件の名前）でも「名前空間の接頭辞」で一致する

テスト: `tests/components/shared/test_query.py` の `TestFlatten.test_unwinds_array_attribute` と `test_renames_to_as`。

## 句の書き方

### `as:` は、名付ける対象が同じマッピングに書いてある句では省略でき、無い句では必須

`flatten.as` / `join.as` / `select.as` が名付けるのは、同じマッピングの `of:` / `to:` / `item:` が指すものそのもので、その名前を既定にしても意味が外れない。`grouped.as` が名付けるのはグループの行の一覧で、`by:` はその行を束ねる鍵であって一覧の名前ではないので、借りられる名前が無い。

テスト:

- 必須: `tests/components/preprocess/test_query_deriver.py` の `TestBuildViewSchema.test_grouped_missing_as_rejected`
- 省略可: `tests/components/preprocess/test_query_normalizer.py` の `TestNormalizeFlatten.test_object_form_as_defaults_to_of`、`TestNormalizeJoin.test_as_defaults_to_to`
- 同じく `select`: 同ファイルの `TestNormalizeSelect.test_as_defaults_to_item`

### `where` に `neq` は無く、否定は `not` に集める

データモデルでは、値が無いことはキーの省略で表す（[JSON データモデル](../20-internal/30-communication/10-json-data-model.md)）。`neq` を入れると、キーが欠けたレコードをどう扱うかの読み方が三つあり、答えが割れる:

- 実データの ≠ と読めば真（値が無いので x とは異なる）
- SQL の三値論理と読めば UNKNOWN で、`where` では落ちる
- `eq` の否定と読めば真（`eq` が偽なので反転して真）

どれを採っても、他の読み方を期待した利用者には不自然に見える。

代わりに二つの規則で意味を一つに決める。atomic 述語は欠けたキーに対して常に偽（`exists` を除く）、`not` は内側の結果を反転する。「等しくない」は `not: { field: x }` と書き、欠けたキーの行は残る。否定の挙動は `not` 一箇所に集まり、述語ごとに考えなくてよい。

テスト（`tests/components/shared/test_record_predicate.py`）:

- atomic 述語が欠けたキーで偽: `TestOperatorEvaluate.test_missing_key_fails_every_operator_but_exists`、`TestFieldPredicateMatches.test_missing_key_observable_via_exists`
- `not` で行が残る: `TestCombinators.test_not_on_missing_key_keeps_record`

### `sort` の欠けたキーは `missing:` で置き、`direction` とは独立に既定で末尾

語は `null` ではなく `missing`。データモデルに null 値の概念は無く、`where` も存在判定を `exists` で表すので、ここだけ SQL の `NULLS FIRST/LAST` を借りると語彙が不揃いになる。Elasticsearch の `missing: _first/_last` と同じ。

位置は `direction` と独立したパラメータで指定する（PostgreSQL や pandas の流儀）。MySQL や MongoDB のように null を最大値や最小値に固定して方向から導く流儀は、「null は値の一種」という前提がデータモデルに合わない。

既定を方向に依らず末尾にするのは、「欠けたキーは末尾」が `asc` でも `desc` でも成り立ち、利用者が「null は値として何位か」を覚えなくてよいため。

テスト: `tests/components/shared/test_query.py` の `TestSort.test_direction_missing_matrix`。

### ドットは入れ子を意味し、出力にドット入りのキーは生まれない

DSL の名前は読みも書きもパスで、ドットは入れ子を表す。読む側の名前（`from`、`flatten.of`、`on`、`where` のキー、`grouped.by`、`select.item`、`sort.by`）は入れ子のオブジェクトを辿る。

書く側の名前（`flatten.as`、`join.as`、`select.as`、`grouped.as`、`grouped.by` の書き戻し先、ビュー名）にドットを書けば、出力はその位置に入れ子になり、途中のオブジェクトが無ければ作る。ビュー名の場合は、そのオブジェクトがルートの属性としてカタログにも立つ（`docs/reference/view.md` の Nested views）。

書き込みが重なるときの規則は MongoDB の projection と TOML の dotted key と同じ:

- 兄弟への書き込み（`a.b` と `a.c`）は一つのオブジェクトに合流する
- 片方が他方の先頭部分になる書き込み（`a` と `a.c`）はエラー。セグメント単位で見るので、`hobby` と `hobbyist` は重ならない

ビュー名どうし、ビュー名と最上位のデータ entity の衝突もこの規則で見る。

テスト:

- 別名スロット: `tests/components/shared/test_query.py` の `TestSelectItem.test_dotted_alias_nests` と `test_siblings_converge_on_one_parent`
- 重なりの検査: 同ファイルの `TestSelectDerive.test_raises_when_any_two_aliases_overlap` と `TestFlattenDeriveOverlap`
- ビュー名: `tests/components/preprocess/test_query_deriver.py` の `TestSourceNameConflicts.test_overlap_is_segment_wise` と `TestDeriveQueries.test_dotted_views_fold_into_a_made_up_object`
