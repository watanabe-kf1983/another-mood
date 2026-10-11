# Document Generator

## Internal Design

### ノードメタデータ

> **[W4 dup]** 表 ↔ data_tree.py:29-163 の各 docstring (a, 完全。正本宣言付きで表を保持)。引用「直接触らせない」↔ data_tree.py:1-5、meta_templates.py:104-111、60-trust-model:114、10-json-data-model:63-66 (完全)。案: 表は削除→コード、残すのは「テンプレートは触れない、出口はフィルタ」の不変条件。引用は削除 (差分「meta に改名しない理由」は data_tree.py コメントへ)

Generator はロードしたデータを inert に詰め替えたうえで `wrap_tree` でラップし、各ノードにシステム由来のフィールドを注入する。テンプレートは元データを Mapping / Array として直接走査し、これらのフィールドには**触れない** — 必要な値はフィルタが取り出して渡す。

| フィールド | 対象ノード | 内容 |
|---|---|---|
| `_parent` | 全ノード | データツリー上の直近の親ノード |
| `_parent_record` | Mapping のみ | 最も近い Mapping 祖先（間の Array を 1 段飛ばす） |
| `_meta.anchor_path` | 全ノード | このノードのアンカーパス（[anchor-spec.md](30-anchor-spec.md)） |
| `_meta.fragment` / `_meta.stamps_anchor` | 全ノード | リンクの着地 fragment と `<a id>` 刻印の要否（由来型ごとの anchor strategy が決める） |
| `_meta.object_type_id` | 全ノード | スキーマ位置を表すカタログ形 ID（Array 要素は `X.item`、singleton は `X`、Array は `X.item[]`） |

> **[W4 → appendix]** (この引用段落)

> **背景: なぜテンプレートから直接触らせないか.** テンプレートエンジン (minijinja) は `_` 始まりの **Python 属性**を undefined にし、メソッド呼び出しは拒否する（データ側の `_` 始まりキーは通る）。`row["_meta"]` も `attr()` も同じく undefined になるので迂回路は無い。これはホスト側の内部にテンプレートを触らせないという信頼モデルの意図そのもので、押し戻す理由がない。
>
> かといって prefix を外して `meta` 等にはしない。ノードは dict / list のサブクラスで、テンプレートからの `row.meta` は getitem を先に引くため、データ側に `meta` キーがあると静かにそちらが勝つ。`_` prefix はまさにこの shadowing を防ぐためにあり、Python 側では load-bearing なまま残す。したがって prefix は据え置き、**テンプレートへの出口だけをフィルタに移す**。
>
> 実際の消費者はこれで足りる: テンプレートからの実需はメタテンプレートの診断テーブルが描くアンカーパス列 1 箇所だけで、それはメタテンプレート専用フィルタ `anchor_path`（ノード → 文字列）が担う。残りの `_parent` / `_parent_record` / `_meta.object_type_id` は `render` の subtree guard・`page_path`・アンカー合成が Python 側で読むだけで、テンプレートからは元々使われていない。

ラップ対象（id 無し Array 要素・ネスト Array は inert container のまま除外）、`_parent` / `_parent_record` の二系統セマンティクス、`anchor_path` / `_type_path` の `cached_property` による再帰合成（amortized O(depth)）、prose 例外といった厳密な規則は `data_tree.py` の docstring が正本。

### render ループ

> **[W4 dup]** ↔ generator.py:68-77,155 (a, 完全)。機構。案: 削除→コード、「メタを特別扱いしない」意図はコードコメントへ

`generate()` は 2 サーフェスを出す:

- **表紙**（`{outDir}/index.md`）— deliverable を列挙する root ランディング。**データモデルを描かない**単発 render（edition ではなく、reconcile の build-report ページと同類）なのでデータ edition ループの外。
- **データ edition**（メタ=`__db/` + ユーザ）— データモデルを描く。メタもユーザも同じ `Edition` 型なので**単一ループ**で回し、メタを特別扱いする分岐を持たない。

各 `Edition` の差分フィールド（`paging` / `name` / `templates_dir` / `root_template` / `extra_filters` / `mirror_blobs`）と render 本体は `edition.py` / `generator.render_edition()` の docstring が正本。`root_template` は当面 `index.md` 固定で、[Edition 別ルートテンプレート（将来）](40-output-layout.md#edition-別ルートテンプレート将来)の継ぎ目。

### Reconcile

> **[W4 dup]** ↔ 40-communication/index.md:21 (c, ほぼ同文)、10-architecture:46-47 (c)、generator.py:84-100 (a)、30-template-spec:49、40-paging:44,49 (c) — 完全。案: ここを正本、communication/index 側をポインタ化（index 側は W4 で処理済み）。末尾順序の理由は残す

Reconcile は Generator の直後に位置するステージで、「Generator の出力（あるべき姿）」と「上流から伝播してきた `BuildReport`（実際に何が起きたか）」を突き合わせ、ユーザに見せる最終出力を確定する役割を持つ。

- エラー無し: Generator の出力をそのまま reconcile の出力ディレクトリに通す（pass-through）
- エラー有り: Generator の出力を破棄し、内蔵の `build_report/build_failure.md` テンプレートでエラーページを `index.md` にレンダリングする

奥付は両方の分岐に付ける。失敗ページは表紙を置き換えるので、失敗時に読者が見る唯一のページになるため。表紙側で生成側（cover テンプレート）に build info を渡さないのは、末尾に何がどの順で並ぶか（**本文 → 奥付リンク → 警告リンク**）を Reconcile 一箇所で決めるため。

条件付きで現れる警告リンクを末尾に置くのは、**常設セクションの位置が警告の有無で動かない**ようにするため。奥付がページ末尾の表だった頃は「本の奥付」として最後が自然だったが、リンク節になった以上その理由は無い。

この分離により以下が成立する:

- Generator は「views を Markdown に変換する」純粋な責務に集中できる（エラー時の出力差し替えロジックを持たない）
- 下流の site / publish ステージは Reconcile の出力の単一視点を持てばよく、エラー時と正常時の分岐を知らなくてよい

#### 命名について

> **[W4 → appendix]**

「reconcile（突き合わせる）」は本リポジトリ独自の語ではなく一般的な英単語だが、ドキュメントビルダーの文脈では珍しい語であり、馴染みのある語が引き起こす意味の取り違えを避ける狙いで採用した。読み手はこの定義に立ち戻ることで、Reconcile ステージの責務を一意に把握できる。
