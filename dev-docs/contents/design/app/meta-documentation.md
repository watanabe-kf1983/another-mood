# メタドキュメンテーション

ユーザが書いたスキーマ定義とクエリ定義を、ツールが内蔵のテンプレートで自動的に
可視化する機能。

## Entity と ObjectType

データカタログのエントリは 2 階層で表現される:

- **Entity**: データツリー上の到達経路を表す identifier `id` (例: `categories.tasks`)。クエリ DSL の `from:`、URL/anchor、ファイルパス、表示見出しに使う
- **ObjectType**: Entity の中の 1 つの item の型 `id` (例: `categories.item.tasks.item`)。コレクションを 1 段降りるごとに `.item` を付加。FK 参照や型レベルの cross-reference に使う

Entity は自身の `item_type` フィールドを通じて ObjectType を保持する。

詳細は [schema-spec.md](../normalizer/schema-spec.md)「Entity 名」節を参照。

ObjectType の表示名 (例: `Category`) を `title:` キーワードから供給する仕組みは別タスク (M4) で導入予定。それまでは Entity.id をそのまま表示する。

## 自動生成される内容

ビルドのたびに、以下が `out_dir` 配下に出力される。出力先のディレクトリ名は `__`
で始まり、ユーザのコンテンツと視覚的に分離される。

- `index.md` — メタドキュメンテーションの一覧インデックス
- `__meta_entity/{id}.md` — エンティティのスキーマ (フィールド一覧、型、参照等)
- `__table_view/{id}.md` — エンティティの実データ一覧
- `__meta_query/{id}.md` — クエリの Definition + Shape + Results

ER 図 (F4) は未対応。

## Entity と Query のページ構成 (非対称)

Entity と Query でページ分け方が異なる:

| 種別 | ページ構成 |
|---|---|
| Entity | `__meta_entity` (Schema) と `__table_view` (Data) の **2 ページ**、相互リンクで往復 |
| Query | `__meta_query` に Definition / Shape / Results の **3 セクション 1 ページ** |

### 背景: なぜ非対称か

**artifact の結合度**で決めている。

**Entity** は Schema と Data が独立した user source:

- Schema: user が JSON Schema として authoring した定義
- Data: user が YAML として authoring したレコード
- どちらも単独で意味を持つ (「このフィールドは何?」 vs 「このレコードは?」)
- → **分離 2 ページ**、それぞれ別の読者の問いに答える

**Query** は Definition / Shape / Results が 1 つの recipe 由来の束:

- Definition: user が書いた DSL
- Shape: Definition から deterministic に推論 (E7 の `apply_to_catalog`)
- Results: Definition + 上流データから生成
- どれも単独では不完全: Definition は抽象 recipe、Shape は「結果の形」単独で
  意味が薄く、Results は Definition 無しに「何のクエリか」分からない
- → **統合 1 ページ**、3 者がセットで初めて意味を成す

Entity の Data を見て味見して Schema を直すことは普通はないが、Query の Results
を味見して DSL (Recipe) を修正するのは日常。Author の feedback loop が
そのまま結合度の差を裏付けている。

### 業界ツールとの対応

- **DBeaver / Snowsight / MS Access のテーブルブラウザ**: Schema (DDL / Properties)
  と Data (Datasheet) は別タブ — 本ツールの Entity 2 ページに対応
- **SQL エディタ + Results pane** (DBeaver の SQL Editor, Snowsight の worksheet):
  Query と Results は同ウィンドウ上下 — 本ツールの Query 1 ページに対応

この非対称は artifact 結合度の差を反映しており、業界慣例とも整合する。

## Query View の Shape が必須な理由

本ツールは複合型 (object / object[]) を許容するため、カラムヘッダと
サンプル行だけでは結果形状が伝わらない (`tasks` カラムが scalar 文字列なのか、
`categories.tasks` 型の配列なのかが値だけでは断定できない)。

Shape セクションで各出力フィールドの型 + entity ref を明示する
ことで、template 著者 / MCP 経由の LLM / 人間の読者すべてに対して型情報が
programmatic に伝わる。SQL クライアントが (全カラムスカラ前提で) 型表示を
省略できるのと対照的。

Shape は E7 の `apply_to_catalog` が生成する (詳細は
[composer.md](../../internal/components/composer.md) の「Query Object の双対性」
節を参照)。

## Results の drill-in は B1-B6 + C3 完成まで暫定

現在の Table View は「全親から flatten した子 Table View」一枚のみで、
親コンテキストが失われる (例: `categories.tasks.md` は全カテゴリのタスクを
一列に並べるだけで、どのカテゴリの task かが判別不能)。B1-B6 (anchor) +
C3 (per-record 詳細ページ) 完成後、「特定親の子 records だけを見る」
navigation が実現する。それまで Query View の Results も同じ暫定レベル。
