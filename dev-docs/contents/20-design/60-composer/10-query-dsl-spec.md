# Query DSL Specification

## External Design

ビューは、エンティティや他のビューから新しいレコードの集合を導く名前付きのクエリで、テンプレートからはエンティティと同じように読める。句は固定順のパイプラインとして評価し、入れ子のまま書かれたデータを別の軸で束ね直すのもこのパイプラインの中で行う（[データモデルの制約](../../10-concept/10-product.md#データモデル-規律を与えた-json-の木)）。句ごとの文法と挙動は `docs/reference/view.md` が正本。以下は、その背後にある判断。

- 句の順序は固定し、収まらない形は別ビューに分割して名前付き参照でつなぐ。インラインサブクエリは採らない（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#ビュー間参照に名前付き参照を採りインラインサブクエリを採らない理由)）。評価順は参照関係から決まり、定義の並び（`__definition.views`）は変えない。中間ビューがテンプレートとメタドキュメントに見える制約は受容する
- 行の数を変えるのは `flatten` 系だけ。ソースに元からある配列は top-level の `flatten:` が、join が作った配列は join 内の `flatten:` が開く（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#flatten-句を-intrinsic-配列専用とした理由)、[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#join-の-inline-flatten-を採用した理由)）
- flatten 後の行は親の属性を残し、要素を `as:` の名前の下に置く（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#flatten-後の-row-shape-に-namespace-保持を採用した理由)）
- `as:` はソースを同じマッピングに書く句（`flatten.of` / `join.to`）では省略可、書かない句（`grouped`）では必須（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#grouped-の-as-を必須にした理由)）
- 欠落キーは data model の「nullable = キー省略」（[json-data-model.md](../40-communication/10-json-data-model.md)）に揃える。`neq` を持たず否定は `not` に集約し（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#where-の-closed-set-から-neq-を外した理由)）、sort は `missing:` で位置を指定して `direction` と直交にする（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#sort-の-keyword-に-null-ではなく-missing-を採用した理由)、[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#sort-の-direction-と-missing-を直交にし既定を-direction-非依存にした理由)）
- `sort` を `select` の後ろに置く（[先例](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#sort-を-select-の後ろに置く先例)）
- DSL の名前は読みも書きもパスで、ドットは入れ子を意味する。別名スロット（`flatten.as` / `join.as` / `select.as` / `grouped.as`、および `grouped.by` の書き戻し先）にドットを書けば出力は入れ子になり、view 出力にドット入りキーは生まれない。兄弟への書き込み（`a.b` と `a.c`）は一つの object に合流し、片方が他方の先頭部分になる書き込み（`a` と `a.c`）は重なりとしてエラーにする。MongoDB の projection と TOML の dotted key と同じ意味論

### スコープ外: nested-list 操作

下記は本ツールではサポートしない。 追加シンタックスが必要で、当面実現予定はない:

- **ツリー shape 出力** (例: 各 category の tasks 配列内で phase を FK 引きして埋め込む)
- **nested array の中身に対する filter / sort** (例: tasks 配列の中身が特定条件を満たすかで category を絞る)

## Internal Design

各句は、レコード変換（`apply`）とカタログ変換（`derive`）を同じ DSL 断片から対にして持ち、両者が同じパイプラインを通る。これにより、データを評価せずに出力の形（カタログ）が分かる。

`join:` だけは 2 入力 1 出力で、1 入力 1 出力の `QueryNode` には乗せない。`Query.apply` / `Query.derive` がパイプライン順序を直書きして呼び分けるため両者で同じ順序が重複するが、2 入力の句が `join:` 一つしかない現状では、この局所的な特別扱いのほうが抽象階層より軽い（[背景](../../90-appendix/20-design/60-composer/10-query-dsl-spec.md#join-を-querynode-に乗せず特別扱いした理由)）。

## Proposals

### 文書ノード — ドット区切りの view 名 (E17)

#### 問題

「複数の entity / view を束ねた一つのページ」(文書) は、現状 root テンプレート (`index.md`) でしか組めない。サブテンプレートの束縛は主題だけ (template-spec の `this` 束縛) で、`render` の主題は `this` の子孫に限られるため、一つのプロジェクトから複数の文書を別ページとして出す手段が無い。`{% include %}` は root の文脈を共有するので `index.md` の肥大化は分割できるが、ページは作らない (showcase/system-dev-docs-ja の二文書で表面化)。

リンク解決は pre-render で静的に決まる (`page_path` はデータ位置と `file_per` だけから計算する) ので、文書ページに描いた既存ノードへのリンクは実際に描かれたページではなく `index.md` を指す。したがって **文書はデータ位置を持つノードでなければならない**。これが唯一の本質的な要件で、代替案はすべてここで退けた:

- **edition 別ルートテンプレート**: edition は同一 report の体裁違いの概念で、文書の器に使うのは目的外利用
- **予約名 (`root` 等) でデータルートをサブテンプレートに渡す**: 主題以外に触る第二の入口になるうえ、データ位置を持たないのでリンクが壊れる
- **`from: __root` のクエリ**: `select` 必須、単一レコード出力、使える句の制限、と特例が積み重なり、DSL の中に別物が同居する
- **第二の view 文法 (`compose:` で source 名を束ねる)**: 文書をノードとして立てられるが、view-schema の oneOf・専用の derive / apply・コピーの型 ID から元の型を引く索引、と新しい機構が一式要る。下記の案は同じ結果をすでにある機構の組み合わせで得るので、こちらを退けた

#### 案: view 名をパスとして読む

view 名のドットを **書き込みパス** と定義する。E14 で「DSL の名前は読みも書きもパス」としたが、view 名だけは view-schema の `propertyNames` がドットを拒んでいる。この例外を外すと、view は root 直下だけでなくデータ木の任意の新しい位置に置ける:

```yaml
# definition/views/要求仕様書.yaml
要求仕様書.用語集:                       # /要求仕様書/用語集 に 用語 のコピーを置く
  from: 用語
要求仕様書.要求.機能要求:                # 中間の 要求仕様書 / 要求仕様書.要求 は暗黙のシングルトン
  from: 要求_by_ユースケース
要求仕様書.要求.その他の要求:
  from: 要求
  where: { 種別: 非機能 }
```

- **文書とその章節項**: パスの中間セグメント (`要求仕様書` / `要求仕様書.要求`) は、誰も定義していない暗黙のシングルトン (object) として立つ。葉は通常の query view (collection)。文法の追加は無く、`file_per: [要求仕様書.要求]` で章ページに割れる
- **葉はコピー**: `from:` だけの query が source のコピーそのもの。compose 案と違い、葉で `where` / `select` / `sort` も使える。型 ID はデータ木の位置から出る (`要求仕様書` / `要求仕様書.要求` / `要求仕様書.用語集.item[]`)。アンカーパスは `/要求仕様書/用語集/書籍`
- **衝突規則**: 既存の二つの規則をパスに延長するだけで、新しい決め事は無い
    - view 名とデータのトップレベルキーの衝突 → **パスの先頭セグメント** がデータのトップレベルキーなら拒否。collection・シングルトン・スカラを区別せず一つの比較で落ちる。スキーマのシングルトンの下に view を吊る (`システム.x`) ことも拒否になるが、許すには種別の判定と既存ノードへの合流経路が別に要り、拒否のほうが単純
    - E14 の書き込みの重なり規則 (`a` と `a.c` はエラー) → view 名同士にも同じく適用。`a.b` と `a.c` は一つの暗黙シングルトンに合流する
- **並び順**: 暗黙シングルトンの子の並びは、トップレベル view と同じ定義順 (ファイルパス順、同一ファイル内は出現順)。文書の章の描画順はテンプレートが名前で引くのでデータ側の順序は効かず、カタログの属性一覧と JSON の鍵順に現れるだけ
- **評価順**: `from` / `join.to` から出る `source_names()` のまま変更なし。別の query から `from: 要求仕様書.用語集` で葉を読めるのは E14 のパス読みがそのまま効くから。暗黙シングルトン自体 (`from: 要求仕様書`) は collection ではないので、既存の「entity ではない」診断に落ちる
- **テンプレート**: root で `{{ 要求仕様書 | render("要求仕様書.md") }}`。サブテンプレートは主題のフィールドが spread されるので `用語集` を素の名前で読める。文書横断参照はコピー経由 (`node("要求仕様書", "用語集", id)`)。元ノード (`/用語/書籍`) はどこにも描かれない。この作法は docs に明記する
- **カタログ**: 暗黙シングルトンはトップレベルのシングルトンと同じく `__root` の `object` 属性になり、葉は配下のドット名の `object[]` 属性として載る (M13 の受け皿)。`__view_defs` には葉だけが通常の view として載り、暗黙シングルトンには定義が無い。コピーの型 ID → 元の型の索引は不要になる (葉は view から view を導く既存の形と同じ)

#### 波及

- `view-schema.yaml`: `propertyNames` のパターンにドット区切りを許す。同ファイルの `from` の説明文「dots are not a path separator」は E14 以前の記述なので、同時に直す
- query_deriver: 先頭セグメントの衝突チェックと、view 名同士の重なりチェック。`_with_source` を root 直下に吊る形からパスに沿って中間 `object` を作る形へ。`_write_catalog_with_views` の root への属性追記はそのまま
- composer: `sources[name]` にフラットに置く形から、パスに沿って入れ子に置く形へ。`view-results/` のファイル名はドット入りのまま (内部成果物)
- `docs/reference/view.md`: view 名の節にパスの意味を、`from` の節にパス読み (E14 で入っているが未記載) を追加。`docs/reference/template.md` の `render` に文書の例と文書横断参照の作法を追加
- 動機は showcase/system-dev-docs-ja。同 showcase は暫定的に `index.md` の合本で進み、E17 後に文書の殻だけをドット名の view に移す
