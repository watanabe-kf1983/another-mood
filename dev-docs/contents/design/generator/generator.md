# Document Generator

## Internal Design

### 内蔵ルートテンプレート

Generator はユーザの `index.md` テンプレートを直接エントリポイントとせず、内蔵のルートテンプレートを起点とする。ルートテンプレートは以下の 2 セクションを持つ:

1. **メタドキュメンテーション** — 内蔵テンプレートでスキーマ・クエリを可視化（[meta-documentation.md](../app/meta-documentation.md) 参照）
2. **ユーザドキュメント** — ユーザの `index.md` テンプレートを呼び出す

これにより、メタドキュメンテーション・ユーザドキュメントが同じテンプレートシステム上で動作する。

### 出力フォーマットとエスケープ

テンプレートの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数とラッパーフィルタを切り替える仕組みは [output-format-spec.md](output-format-spec.md) で扱う。

### ノードメタデータ

Generator はデータロード直後に views ツリーを `wrap_tree` でラップし、各ノードにテンプレート公開のシステム由来フィールドを注入する。テンプレートは元データを「ちょっと拡張された dict / array」として直接走査する。

| フィールド | 対象ノード | 内容 |
|---|---|---|
| `_parent` | 全ノード | データツリー上の直近の親ノード |
| `_parent_record` | Mapping のみ | 最も近い Mapping 祖先（間の Array を 1 段飛ばす） |
| `_meta.anchor_path` | 全ノード | このノードのアンカーパス（[anchor-spec.md](anchor-spec.md)） |
| `_meta.object_type_id` | 全ノード | スキーマ位置を表す catalog 形 ID（Mapping は `X.item`、Array は `X.item[]`） |

ラップ対象（id 無し Array 要素・ネスト Array は素の dict / list として除外）、`_parent` / `_parent_record` の二系統セマンティクス、`anchor_path` / `_type_path` の `cached_property` による再帰合成（amortized O(depth)）、prose 例外といった厳密な規則は [data_tree.py](../../../../src/another_mood/components/generator/data_tree.py) の docstring が正本。

### anchor_path → ノードマップ

リンク解決はアンカーパスからノードを引く。`build_node_map` がラップ済みツリーを `iter_nodes` で 1 度舐め、`{anchor_path: node}` のフラットなマップを構築する。キーを full anchor_path にすることで prose の `/` 素通し例外 ([anchor-spec.md](anchor-spec.md#prose-の例外)) を各ノードの `anchor_path` 構築側 1 箇所に閉じ込め、マップ側に特別扱いを要さない。実装は [data_tree.py](../../../../src/another_mood/components/generator/data_tree.py) の `build_node_map` / `iter_nodes` docstring が正本。

### ページパスの導出

ノードの**表示先ページのパス** (レポートルート相対、fragment 抜き) を求める。page_path は **`(node, file_per 設定)` の関数**であってノード単体の内在属性ではないため `_meta` には焼かない — 消費側 (リンク解決フィルタ、`{% mood_view %}`) が render ごとに config を受け取り、必要時に `config.page_path(node)` を呼ぶ。

paging ポリシー (どの object type が分割境界か、root→`index.md` / 分割対象→`{anchor_path}.md`) を知る `Edition.page_path` に実装を置き、構造的な木の遡上だけは data_tree の free function `nearest_ancestor` に分離する (config は paging を知らない木に触れず、data_tree は paging を知らないまま保つ)。座標系をレポートルート相対に取る理由を含め、導出規則とコードは [edition.py](../../../../src/another_mood/components/generator/edition.py) の `Edition.page_path` docstring が正本。

### リンク解決

> 基盤の [anchor_path → ノードマップ](#anchor_path--%E3%83%8E%E3%83%BC%E3%83%89%E3%83%9E%E3%83%83%E3%83%97) を使う。リンクの仕様（リンク記法 / フィルタ API / 解決のタイミング / 未解決時の挙動）は [anchor-spec.md](anchor-spec.md) を参照。

リンク解決は pre-render 段階で完結する (post-render の文字列置換は採らない)。フィルタは依存方向で 2 群に分かれる: フォーマット非依存の中立フィルタ (`node` / `label`) はノードマップだけに束縛され、フォーマット固有の `link` / `href` / `anchor` / `relink` は `Edition` に束縛される。source ページ（主題ノード）はコンテキストの `this` から得る。実装契約 — `link` / `href` / `relink` に `@pass_context` が要る二つの理由（source 取得・定数畳み込み抑止）、`anchor` には不要なこと、`MissingNode` を整形フィルタ側で捌き `node_href` には渡さないこと — は [data_tree_filters.py](../../../../src/another_mood/components/generator/data_tree_filters.py) / [output_formats/md.py](../../../../src/another_mood/components/generator/output_formats/md.py) の docstring が正本。

#### prose body 処理フィルタ

Markdown データソースの body には、Normalizer がソース内の相対リンクを `node:` 記法に変換済みのリンクが含まれる ([markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照)。`relink` フィルタが body 内の `node:` リンク先を表示先ページからの相対 URL に置換する。**リンク解決の単一責務**に絞り、見出し深さ調整は `under_heading` と合成する (記法・対象範囲・未解決契約は [anchor-spec.md](anchor-spec.md#prose-body-処理フィルタ-relink) が正本)。

body 内のどこが本物の `node:` リンクかは markdown-it でパースして判定し (レンダラには使わず位置特定のための読み取り専用パーサとして使う)、置換は元文字列への splice で行う。機構の詳細 (`normalizeLink` の恒等化、本物リンクだけが `link_open` になる性質、行範囲限定の splice) は [output_formats/link_resolve.py](../../../../src/another_mood/components/generator/output_formats/link_resolve.py) の docstring が正本。

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

### relink の暗黙適用

> **未実装** — 別タスクとして切り出し（未タスク化）。

`{{ prose.body | relink }}` を author に明示的に書かせる（B5 で実装済み）か、システムが自動的に処理を挟むかは、ノードメタデータ機構 (B1, B3) の延長で検討する余地がある (例: schema が prose body 型を宣言してあればアクセス時に自動処理)。B5 の最低線は明示適用とし、暗黙適用は別タスクとして切り出す。

### mood_view を this の subtree 内に限定する (B12)

> **未実装** — B12。`{% mood_view %}` で `this` の子孫でないノードを inline 埋め込みすると、そのノードの内部相対リンク（`relink` の `node:` 解決 / `link` / `href`）も、そのノードへ張るリンクも壊れる。

**症状**: showcase/music で album に liner note (prose) を `{% mood_view %}` で埋めると、web で liner note 本文中の別アルバムへの `node:` リンクが、埋め込み先アルバムページでなく **root 基準**で相対化されて壊れる（book は単一ページ fragment なので偶然通る）。

**土台となる不変条件**: 各ノードは *データ位置* で一意に定まる 1 ページ（`page_path`）にだけ描かれる。リンク解決はこれに乗る — source は `page_path(this)`、target は `page_path(target)`。inline `{% mood_view %}` で home 外にノードを描くとこの不変条件が破れ、`page_path` が実描画ページと食い違う。

**却下案（source だけを描画ページに寄せる）**: 描画ページを予約キー `__page` でコンテキストに流し、source をそこから取る。だが target 側（`page_path(target)`）は依然データ位置からの**予測**であり、非対称で不整合が残る。単一パス描画では target の実描画ページは引けず（複数箇所に描けば一意にすらならない）、target を予測可能に保つには「描画はデータ位置に従う」不変条件そのものを守るしかない。source を known・target を derived と割り切れるのは両者が同一不変条件下にあるときだけ。→ source を逃がすのでなく、不変条件を**強制**する側に倒す。

**方針**: `{% mood_view %}` に渡す subject は `this` の subtree 内（`this` の子孫）でなければ **file+line 付きのビルドエラー**にする。判定は **node の子孫判定**（subject から `_parent` を辿って `this` に identity 一致するか）で行い、`page_path` も `__page` も要らない。`anchor_path` の文字列 prefix では代用しない — 兄弟でも一方の edge 名が他方の prefix になりうる（例: `/album` と `/album_tracklist`）ので子孫判定と一致しない。非ノード subject（anchor もリンクも持たない）は対象外。mood_view 拡張が `ContextReference` で `this` を読み、parse 時に拾ったタグの file+line を実行時エラーに載せる。docstring で「やるな」と教えるのでなく、踏んだ行を指すエラーで誘導する。

**split / inline を一律に扱う**: 実際にリンクが壊れるのは inline で home 外に描く時だけだが、判定を split / inline で分けると、同じ `{% mood_view %}` 呼び出しが「subject を split する edition では通り、しない edition では弾かれる」ことになり、エラーが edition (file_per) 依存になって利用者を惑わす。妥当性はテンプレート単体（構造）で決めたいので、split でも subtree 外なら弾く。なお条件を `page_path(subject) == page_path(this)` にすると、自分のページに載る正当な split（root から `{% mood_view "album-detail.md" with album %}` 等）まで弾いてしまうため、条件は page_path でなく構造（子孫）に置く。

**利用者側の書き換え**: 他所のノードを埋めたいときは、クエリ（LEFT JOIN 等）で subtree に取り込んで子孫化するか、`| link` で参照する。

**完了条件**:

- `this` の subtree 外のノードへの `{% mood_view %}` が、split / inline を問わずタグの file+line を指すビルドエラーになる。
- showcase/music は liner note を `album_tracklist` にジョインして album の子孫として描き、web で別アルバムへの `node:` リンクが埋め込み先アルバムページ基準で解決する（例: `winter_in_the_machine` ページの Graphite Summer リンク）。
- 実装完了時、[リンク解決](#リンク解決) 節に「各ノードは `page_path` の 1 ページにだけ描かれる」不変条件を Internal Design として明記し、本 proposal を削除する。
