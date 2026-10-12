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

### 合成ビュー (E17)

#### 問題

「複数の entity / view を束ねた一つのページ」(文書) は、現状 root テンプレート (`index.md`) でしか組めない。サブテンプレートの束縛は主題だけ (template-spec の `this` 束縛) で、`render` の主題は `this` の子孫に限られるため、一つのsbdb プロジェクトから複数の文書を別ページとして出す手段が無い。`{% include %}` は root の文脈を共有するので `index.md` の肥大化は分割できるが、ページは作らない (showcase/system-dev-docs-ja の二文書で表面化)。

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
- **カタログ**: 合成ビューはトップレベルのシングルトンで、view の側にはその受け皿がまだ無い (スキーマ側のトップレベル・シングルトンは M13 で `__root` の属性になったが、view はルートの属性になっていない)。`__view_defs` に shape を出し、コピーの型 ID → 元の型 (`type_index`。prose の見出しアンカーに要る) を引くために、トップレベル・シングルトンのカタログ表現が前提。**M13 が前提**。合成ビューを `__root` の属性として吸収するか、view 同様に独立の項目として emit するかは実装時に決める
- **句の名前は仮**。候補: `compose` / `bundle` / `sections`。query 句 (`from` / `flatten` / `join` / `where` / `grouped` / `select` / `sort`) との語感と、composer コンポーネント名との紛れを見て決める

#### 波及

- `view-schema.yaml`: 定義本体を query / compose の oneOf にする
- composer / query_deriver: 合成の derive (カタログ shape) と apply (コピー)。`_with_source` と同じ操作で root に吊る
- `docs/reference/view.md` に合成の節を追加。`docs/reference/template.md` の `render` に文書の例と文書横断参照の作法を追加
- 動機は showcase/system-dev-docs-ja。同 showcase は暫定的に `index.md` の合本で進み、E17 後に文書の殻だけを合成ビューに移す
