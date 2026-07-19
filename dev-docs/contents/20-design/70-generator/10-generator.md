# Document Generator

## Internal Design

### 内蔵ルートテンプレート

Generator はユーザの `index.md` テンプレートを直接エントリポイントとせず、内蔵のルートテンプレートを起点とする。ルートテンプレートは以下の 2 セクションを持つ:

1. **メタドキュメンテーション** — 内蔵テンプレートでスキーマ・クエリを可視化（[meta-documentation.md](../20-app/40-meta-documentation.md) 参照）
2. **ユーザドキュメント** — ユーザの `index.md` テンプレートを呼び出す

これにより、メタドキュメンテーション・ユーザドキュメントが同じテンプレートシステム上で動作する。

### 出力フォーマットとエスケープ

テンプレートの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数とラッパーフィルタを切り替える仕組みは [output-format-spec.md](50-output-format-spec.md) で扱う。

### ノードメタデータ

Generator はデータロード直後に views ツリーを `wrap_tree` でラップし、各ノードにテンプレート公開のシステム由来フィールドを注入する。テンプレートは元データを「ちょっと拡張された dict / array」として直接走査する。

| フィールド | 対象ノード | 内容 |
|---|---|---|
| `_parent` | 全ノード | データツリー上の直近の親ノード |
| `_parent_record` | Mapping のみ | 最も近い Mapping 祖先（間の Array を 1 段飛ばす） |
| `_meta.anchor_path` | 全ノード | このノードのアンカーパス（[anchor-spec.md](20-anchor-spec.md)） |
| `_meta.object_type_id` | 全ノード | スキーマ位置を表す catalog 形 ID（Mapping は `X.item`、Array は `X.item[]`） |

ラップ対象（id 無し Array 要素・ネスト Array は素の dict / list として除外）、`_parent` / `_parent_record` の二系統セマンティクス、`anchor_path` / `_type_path` の `cached_property` による再帰合成（amortized O(depth)）、prose 例外といった厳密な規則は `data_tree.py` の docstring が正本。

### anchor_path → ノードマップ

リンク解決はアンカーパスからノードを引く。`build_node_map` がラップ済みツリーを `iter_nodes` で 1 度舐め、`{anchor_path: node}` のフラットなマップを構築する。キーを full anchor_path にすることで prose の `/` 素通し例外 ([anchor-spec.md](20-anchor-spec.md#prose-の例外)) を各ノードの `anchor_path` 構築側 1 箇所に閉じ込め、マップ側に特別扱いを要さない。実装は `data_tree.py` の `build_node_map` / `iter_nodes` docstring が正本。

### ページパスの導出

ノードの**表示先ページのパス** (レポートルート相対、fragment 抜き) を求める。page_path は **`(node, file_per)` の関数**であってノード単体の内在属性ではないため `_meta` には焼かない — 消費側 (リンク解決フィルタ、`{% mood_view %}`) が render ごとに `PagingPolicy` を受け取り、必要時に `paging.page_path(node)` を呼ぶ。

paging ポリシー (どの object type が分割境界か、root→`index.md` / 分割対象→`{anchor_path}.md`) は `PagingPolicy` (`file_per` ＋ `is_split_target` / `page_path`) が担い、構造的な木の遡上だけは data_tree の free function `nearest_ancestor` に分離する (`PagingPolicy` は paging を知らない木に触れず、data_tree は paging を知らないまま保つ)。`Edition` はこの `PagingPolicy` を保持し、generator だけが full な `Edition` を持つ。座標系をレポートルート相対に取る理由を含め、導出規則とコードは `edition.py` の `PagingPolicy` docstring が正本。

### リンク解決

> 基盤の [anchor_path → ノードマップ](#anchor_path--%E3%83%8E%E3%83%BC%E3%83%89%E3%83%9E%E3%83%83%E3%83%97) を使う。リンクの仕様（リンク記法 / フィルタ API / 解決のタイミング / 未解決時の挙動）は [anchor-spec.md](20-anchor-spec.md) を参照。

リンク解決は pre-render 段階で完結する (post-render の文字列置換は採らない)。フィルタは依存方向で 2 群に分かれる: フォーマット非依存の中立フィルタ (`node` / `label`) はノードマップだけに束縛され、フォーマット固有の `link` / `href` / `anchor` / `relink` は `PagingPolicy` に束縛される。source ページ（主題ノード）はコンテキストの `this` から得る。実装契約 — `link` / `href` / `relink` に `@pass_context` が要る二つの理由（source 取得・定数畳み込み抑止）、`anchor` には不要なこと、`MissingNode` を整形フィルタ側で捌き `node_href` には渡さないこと — は `data_tree_filters.py` / `output_formats/md.py` の docstring が正本。

#### 描画の単一ページ不変条件 (mood_view subtree ガード)

上のリンク解決は次の不変条件に乗っている: **各ノードは *データ位置* で一意に定まる 1 ページ (`PagingPolicy.page_path`) にだけ描かれる**。source は `page_path(this)`、target は `page_path(target)` — 両者が同じ規則でノードのデータ位置からページを引くからこそ、`| link` / `href` / `relink` が一貫して相対化できる。`{% mood_view %}` で `this` の subtree 外にノードを inline 描画するとこの不変条件が破れ、`page_path(subject)` が実描画ページと食い違って、そのノードの内部 `this` 起点リンクも、そのノードへ張る被リンクも壊れる。

そこで mood_view 拡張は、subject が `this` の子孫（subject から `_parent` を遡上して `this` に identity 一致）でなければ、タグの file+line 付きビルドエラーにする。判定は **構造（子孫）** で行い、split / inline や edition (file_per) に依存しない — 妥当性をテンプレート単体で決めたいため（同じ呼び出しが「split する edition では通り、しない edition では弾かれる」ような edition 依存エラーを避ける）。

**非ノード subject は免除**（anchor も page identity も持たない）。ただしこの免除が健全なのは、その子テンプレが `this` 起点の描画（`link` / `href` / `anchor` / `relink`・アンカー刻印）を一切しないときに限る。id 等を受け取り内部でノードを引き直して描く子テンプレはガードの射程外で、リンク正当性は author 責任になる（例: meta の `record_table.md` は entity id を受けてデータ行の表を描くのみで、entity ノード自体は配置しない）。他所のノードを描きたいときはクエリ (join 等) で subtree に取り込んで子孫化するか、`| link` で参照する。導出規則とコードは `mood_view_processor.py` の `_guard_subtree` docstring が正本。

#### prose body 処理フィルタ

Markdown データソースの body には、Normalizer がソース内の相対リンクを `node:` 記法に変換済みのリンクが含まれる ([markdown-parser-spec.md](../50-normalizer/30-markdown-parser-spec.md) 参照)。`relink` フィルタが body 内の `node:` リンク先を表示先ページからの相対 URL に置換する。**リンク解決の単一責務**に絞り、見出し深さ調整は `under_heading` と合成する (記法・対象範囲・未解決契約は [anchor-spec.md](20-anchor-spec.md#prose-body-処理フィルタ-relink) が正本)。

body 内のどこが本物の `node:` リンクかは markdown-it でパースして判定し (レンダラには使わず位置特定のための読み取り専用パーサとして使う)、置換は元文字列への splice で行う。機構の詳細 (`normalizeLink` の恒等化、本物リンクだけが `link_open` になる性質、行範囲限定の splice) は `output_formats/md.py` の docstring が正本。

relink は author が明示的に書く (`{{ prose.content | relink }}`) のを設計とし、システムが暗黙に挟む案は採らない。context を読める自動フックは `template_engine.py` の finalize しかないが、finalize は `Markup` を素通しする一方、`under_heading` 等の Markdown 出力フィルタはその `Markup` を返す。ゆえに暗黙 relink は `under_heading` と合成した瞬間に発火せず、`node:` を silent に出力へ漏らす (値に「relink 未了」の印を持たせて伝播させる代案も、文字列連結・Markup 化で印が黙って落ちるため信頼できない)。明示適用は raw な `node:` content の直近に author が relink を置くから確実で、合成順序も `| relink | under_heading` と見えるまま残る。

### Reconcile

Reconcile は Generator の直後に位置するステージで、「Generator の出力（あるべき姿）」と「上流から伝播してきた `BuildReport`（実際に何が起きたか）」を突き合わせ、ユーザに見せる最終出力を確定する役割を持つ。

- エラー無し: Generator の出力をそのまま `reconcile_dir` に通す（pass-through）
- エラー有り: Generator の出力を破棄し、`__build_failure` テンプレートでエラーページをレンダリングして `reconcile_dir` に書き出す

この分離により以下が成立する:

- Generator は「views を Markdown に変換する」純粋な責務に集中できる（エラー時の出力差し替えロジックを持たない）
- 下流の Render / publish_stage は `reconcile_dir`（= Reconcile の出力）の単一視点を持てばよく、エラー時と正常時の分岐を知らなくてよい

#### 命名について

「reconcile（突き合わせる）」は本リポジトリ独自の語ではなく一般的な英単語だが、ドキュメントビルダーの文脈では珍しい語であり、馴染みのある語が引き起こす意味の取り違えを避ける狙いで採用した。読み手はこの定義に立ち戻ることで、Reconcile ステージの責務を一意に把握できる。

## Proposals

### NodeMeta の由来型分岐を NodeKind strategy へ多態化 (B14)

`_NodeMeta` の複数プロパティに散る型分岐を、由来型で選ぶ strategy object 一箇所へ集約する内部リファクタ。外部挙動・[anchor-spec.md](20-anchor-spec.md) は不変の **behavior-preserving**。H6（blob リンク解決）で `is_blob` 分岐が足されたのが発端だが、狙う対象は H6 以前から在る SEMANTIC 軸の sprawl なので H6 とは別タスクに切る（H6 マージ後に着手）。

**動機 — 分岐は3軸に直交し、SEMANTIC 軸が支配的**

`_NodeMeta` の分岐を discriminant で棚卸しすると、互いに直交する3軸に散る。うち SEMANTIC 軸（`origin_item_type`）が9分岐中5を占め、しかも「見出しか」を3プロパティで**再テスト**している — これが replace-conditional-with-polymorphism の古典的トリガー。

| プロパティ | 分岐 | 軸 |
|---|---|---|
| `anchor_path` | `parent is None` → `/` | ROOT |
| `anchor_path` | 見出し → `{record}#{seg}` / path-based → `safe="/"` | SEMANTIC |
| `fragment` | 見出し → `seg` / blob → `""` / else → `anchor_path` | SEMANTIC |
| `stamps_anchor` | 見出し → `False` | SEMANTIC |
| `object_type_id` | `ArrayNode` → `[]` | STRUCTURAL |
| `_type_path` | `parent is None` → `.item` / 親 `ArrayNode` → `item` | ROOT / STRUCTURAL |

**方針 — 意味の層に多態を落とす**

- `origin_item_type` で選ぶ `_NodeKind`（module-level のステートレス singleton 群: `_HeadingKind` / `_BlobKind` / `_ProseKind` / `_PlainKind`）へ、SEMANTIC な振る舞い（`fragment` / `stamps_anchor` / anchor segment の `safe` 方針 / 見出しの `#slug` 合成）を委譲する。各プロパティ本体から `if` が消え、分岐は `_kind_for(origin_item_type)` ファクトリ一箇所へ集約される。
- `_NodeMeta._kind` は `cached_property` にして lazy dispatch とする。`origin_item_type` は `build_node_map` が全ノードの `anchor_path` を引く過程でほぼ全ノードで計算済みのため、laziness も計算コストも現状据え置き。
- 型を選ぶ discriminant（`origin_item_type`）自体が構造コア（`_type_path` → `object_type_id`）から計算されて出るため、多態は `_NodeMeta` 丸ごとではなく**その上に乗る意味の層**に落ちる。共有の構造コアは残す。

**スコープ（合意済み）**

- **SEMANTIC 軸のみ**を対象とする。
- **ROOT**（`parent is None`）は真の基底ケース（親が無い→基底パスという非対称 bail-out）なので guard clause 据え置き。プロジェクトの guard 規約（[style-guide](../../30-dev/40-style-guide.md) / DEVELOPMENT.md）に合致。
- **STRUCTURAL**（Array/Mapping）掃除は**しない** — 既に `ArrayNode` / `MappingNode` で多態化済みの別軸で、同じ階層に混ぜない。`object_type_id` / `_type_path` の `isinstance` は現状維持。

**検証** — 公開属性（`anchor_path` / `fragment` / `stamps_anchor` / `object_type_id` / `origin_item_type`）の振る舞いが不変の behavior-preserving リファクタ。既存テスト群と anchor 不変条件がガードになり、各ステップ緑を保って刻める。

実装完了時、維持価値のある設計判断（3軸の直交・多態を意味の層に落とす理由）は `data_tree.py` の docstring へ移し、この Proposal は削除する。
