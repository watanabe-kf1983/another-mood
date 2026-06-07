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

Generator はデータロード後、views データツリーをラップしてテンプレートからアクセスできるシステム由来のフィールドを注入する。テンプレートは元データを「ちょっと拡張された dict / array」として直接走査する。

#### 公開フィールド

| フィールド | 対象ノード | 内容 |
|---|---|---|
| `_parent` | 全ノード | データツリー上の直近の親ノード。Array 要素なら Array、Array なら親 Mapping、Mapping なら親 Mapping。root では `None` |
| `_parent_record` | Mapping のみ | 最も近い Mapping 祖先。Array 要素から見て Array を 1 段飛ばして親 Mapping を返す。Mapping 自身が dict 直下のキーなら `_parent` と同じ |
| `_meta.anchor_path` | 全ノード | このノードのアンカーパス文字列 ([anchor-spec.md](anchor-spec.md) の規則に従う)。root を `/` とする絶対パス |
| `_meta.object_type_id` | 全ノード | このノードのスキーマ位置を表す path 形 ID。Mapping は ObjectType ID (`X.item`)、Array は field path 形 (`X.item.yyy`、catalog 表記 `X.item.yyy.item[]` の同義)。root は `.item`（`data_catalog._item_type_id([])` が空 edge path に返す値＝root オブジェクトの型 ID） |

対象範囲は anchor path 付与可能な全 Mapping / Array ノード ([anchor-spec.md](anchor-spec.md) 参照)。リスト要素に `id` フィールドが無い場合はその要素も配下もアンカーパスを持たないため、ラップ対象から除外する (= 親参照を持たない素の dict / list として残る)。Array 配下の Array も同様にラップ対象外 — アンカー上の位置を表す手段がないため、生 list として通す。

利用例:

```yaml
# generator 入力データ
categories:
- id: G
  title: CLI / 設定システム
  tasks:
  - id: G1
    title: mood init コマンド (プロジェクト初期化)
```

```jinja2
{{ task._parent }}                  {# tree-walk: array `tasks` 自身 #}
{{ task._parent_record.title }}     {# skip-array: 親の category dict → "CLI / 設定システム" #}
```

#### 背景: parent の二系統セマンティクス

データツリー上の親参照は、利用文脈に応じて自然な意味が二通りある:

- **直近の親ノード** (`_parent`): ツリーの直近上位ノードへのエッジ。Array 要素から見れば Array、Array から見れば親 Mapping。データツリーの構造を素直に反映
- **最も近い Mapping 祖先** (`_parent_record`): 子要素から「自分が属するレコード」を取得する場面で自然。Array 要素 → 親 Mapping が 1 hop で書ける

両系統を明示的に提供することで「親」の意味を読み手・書き手の双方が誤読しないようにする。

#### 実装

- ラップ方式: `dict` / `list` の薄いサブクラス (`MappingNode` / `ArrayNode`) を `_parent` 属性付きで定義。`_parent_record` は `MappingNode` 上の lazy property として `_parent` を 1〜2 段辿るだけで決まる
- 共通プロトコル: `Node` Protocol が `_parent: Node | None` と `_segment: str` を定める。両ラッパーが構造的に満たす。`_segment` は「親から見たこのノードへの edge ラベル」で、wrap 時に決まる (singleton/Array なら親 dict の key、Mapping element of Array なら自身の `id` 値)
- 注入タイミング: Generator のデータロード直後 (`load_model` の戻り値を `wrap_tree` でラップ)。preprocess / composer の出力データには現れない
- 属性は dict / list の要素として現れないため、`{% for k, v in obj.items() %}` や YAML ダンプには混入しない (PyYAML は `add_multi_representer(dict, ...)` / `add_multi_representer(list, ...)` で subclass を represent_dict / represent_list に流す登録のみ追加すれば、ラッパーごと素の dict / list として出力される)

##### `_meta` の計算

- `_meta` は wrap 時に各ノードへ eager に確保。中身の `anchor_path` / `object_type_id` が `cached_property` で初回のみ「親の同名値 + 自分の `_segment`」という単純な再帰合成で求まる (親側も同様に cached なので全体 amortized O(depth))
- anchor_path の root は `/`、それ以外は親パス + escape 済み segment。`_segment` は `urllib.parse.quote` で percent-encode して `/` で join。**prose 例外** ([anchor-spec.md](anchor-spec.md#prose-の例外)): 自身の `object_type_id == "prose.item"` のときに限り `/` を escape **しない**。escape ルールの差は型レベルの仕様なので、`object_type_id` を直接見るのが素直
- object_type_id は `.` で join。Mapping element of Array だけ schema 上のスロットが定数 `item` になるので segment を上書きする (それ以外は `_segment` をそのまま使う)。root は `.item`。ただしトップレベル entity は catalog root (`parent_entity=None`) なので、root の id は子の prefix に**しない** — 合成上 root は空 prefix を寄与する

### anchor_path → ノードマップ

リンク解決 (B4 / B5) は anchor path からノードを引く。`build_anchor_map` が `wrap_tree` の戻りを `iter_nodes` で 1 度舐め、`{_meta.anchor_path: node}` の**フラットなマップ**を構築する。root は `["/"]` で取れる ([anchor-spec.md](anchor-spec.md#id-体系) の root = `/` 不変条件に依拠)。

- **キーは full anchor_path** にする。これにより prose の `/` 素通し例外 ([anchor-spec.md](anchor-spec.md#prose-の例外)) はマップ側に特別扱いを要しない — 各ノードの `anchor_path` が構築時点で prose 規則を吸収済みで、その文字列をそのままキーにするだけで引ける。escape / prose 規則を構築側 1 箇所に閉じ込める方針と整合する
- **アンカー対象集合の再導出をしない**。`iter_nodes` はラップ済みツリーを舐め、子が `Node` (= `MappingNode` / `ArrayNode`) のときだけ降りる。id 無し Array 要素・ネスト Array は素の dict / list なので自然に除外され、「どれがアンカー対象か」の判定は wrapping 側の 1 箇所に保たれる
- **`iter_nodes` は free function**。`_` プレフィックスはノードのテンプレート公開フィールド専用 ([data_tree.py](../../../../src/another_mood/components/generator/data_tree.py) 冒頭参照) なので、内部専用の走査をノードのメソッドにすると命名規約と衝突する。同じ理由で、上昇方向の走査 (`_parent` を遡る `nearest_ancestor`、[ページパスの導出](#ページパスの導出-b6) B6) も free function にする

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

### ページパスの導出 (B6)

> **実装済** — Phase 11 タスク [B6](../../../tasks.md)。`ReportsConfig.page_path` / `nearest_ancestor` として実装。消費する B4/B5 (リンク解決) は未実装。

ノードの **表示先ページのパス** (レポートルート相対、fragment 抜き) を求める。page_path は **`(node, file_per 設定)` の関数**であってノード単体の内在属性ではないため、`_meta` には焼かない。消費側 (リンク解決フィルタ B4/B5、`{% mood_view %}` C4) はいずれも render ごとに config を closure binding で受け取る ([リンク解決](#リンク解決-b4-b5)) ので、必要時に `config.page_path(node)` を呼べば足り、全ノードへ事前計算して配る必要がない。

`page_path` は [`ReportsConfig`](paging-spec.md) のインスタンスメソッドに置く — 「どの object type が分割境界か (file_per)」「root→`index.md` / 分割対象→`{anchor}.md`」という paging ポリシーを知るのは config だから。構造的な木の遡上だけは data_tree 側の free function `nearest_ancestor(node, match)` (`self` を含め `_parent` を遡り `match` を最初に満たすノード、無ければ `None`) に切り出し、config は paging を知らないツリーに触れず、data_tree は paging を知らないまま保つ:

```python
# reports_config.py
def page_path(self, node: Node) -> str:
    page = nearest_ancestor(node, lambda n: self.is_split_target(n._meta.object_type_id))
    if page is None:                    # 分割境界が無い → root ページ
        return "index.md"
    return page._meta.anchor_path.removeprefix("/") + ".md"
```

導出規則:

- **非 root の分割対象ノード**: 自身の anchor_path の先頭 `/` を落として `.md` を付けたもの (例: `/erds/user-management` → `erds/user-management.md`)
- **root**: `index.md` 固定。root は分割境界の探索が `None` を返す (file_per に root 型は載らない) 終端なので常にページになる。generic な `{anchor_path}.md` 式が root では退化する (`/` → `.md`) のも、この `None`→`index.md` 特例で吸収される
- **非分割対象ノード**: `nearest_ancestor` が最寄りの分割境界 (無ければ `None`=root) を返し、その page_path に解決される

「root が常にページ」という paging 事実は config 側の `None`→`index.md` 解釈に閉じ込め、`nearest_ancestor` は構造的な「最寄り一致」だけを返す。

座標系は **レポートルート相対**。`reports/` および profile 段 ([paging-spec.md](paging-spec.md#出力ディレクトリ規約)) は実ファイルを書き出す mood_view 側 (C3) が被せるマウント先で、page_path には含めない。リンク解決は source/target 双方の page_path の相対差 (`os.path.relpath`) のみを使うため、共通のマウント先は相殺され、原点をレポートルートに取って問題ない。

page_path も結合済み URL もノードに焼かないのは同じ理由 — どちらも config やリンク文脈に依存し、ノード単体には属さない。URL は `(source page_path, target page_path, target anchor_path)` の三項で決まるので、anchor 解決フィルタが必要時にその場で組む (詳細は [anchor-spec.md#リンク解決](anchor-spec.md#%E3%83%AA%E3%83%B3%E3%82%AF%E8%A7%A3%E6%B1%BA) 参照)。

### リンク解決 (B4, B5)

> **B4 実装済 / B5 未実装** — anchor 解決・整形フィルタ (B4) は実装済み。prose body `resolve` フィルタ (B5) は未実装。anchor_path → ノードマップ (B2) も実装済 — [anchor_path → ノードマップ](#anchor_path--%E3%83%8E%E3%83%BC%E3%83%89%E3%83%9E%E3%83%83%E3%83%97) 参照。アンカーの仕様 (リンク記法 / フィルタ API / 解決のタイミング / 未解決時の挙動) は [anchor-spec.md](anchor-spec.md) を参照。

リンク解決は pre-render 段階で完結する (post-render の文字列置換は採らない)。フィルタは依存方向で 2 群に分かれる: フォーマット非依存の中立フィルタ (`anchor` / `anchor_path` / `label`) は anchor マップだけに束縛され `anchor.make_anchor_filters(anchor_map)` が供給する。フォーマット固有の `link` / `href` は `ReportsConfig` に束縛され `md.make_link_filters(config)` が供給する（`OutputFormat.link_filters` 経由でフォーマットに属し、Environment 構築時に config で配線される）。source / target のページパスは `config.page_path(node)` (B6) で算出する — source は `@pass_context` フィルタがコンテキストの `this`（主題ノード）から、target は anchor マップで引いたアンカーから (詳細は [anchor-spec.md#リンク解決](anchor-spec.md#リンク解決))。

#### anchor 解決・整形フィルタ (B4)

`anchor()` で **アンカー**（リンク可能なオブジェクト）を得て、整形フィルタで Markdown リンク / display 文字列 / URL を生成する:

- `anchor(seg, *segs)` — segments（各 escape）か `/` 始まりの出来合いアンカーパスから、アンカーを得る（関数・フィルタ両用）
- `link` / `label` / `href` — アンカー → `[<display>](<URL>)` / display 文字列 / URL（`link(text)` で override）
- `anchor_path(seg, *segs)` — 解決せずアンカーパス文字列を返す

仕様は [anchor-spec.md](anchor-spec.md#リンク記法) を参照。

#### prose body 処理フィルタ (B5)

Markdown データソースの body には、Normalizer がソース内の相対リンクを `toc:` 記法に変換済みのリンクが含まれる ([markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照)。仮称 `resolve` フィルタが body 内の `toc:` URL を実 URL に置換する。

このフィルタは anchor 解決以外にも、見出しレベル正規化やエスケープ調整等の prose body 固有処理を兼ねる総合処理フィルタとして位置付ける (具体仕様は別途)。

##### 暗黙適用は別途検討

`{{ prose.body | resolve }}` を author に書かせるか、システムが自動的に処理を挟むかは、ノードメタデータ機構 (B1, B3) の延長で検討する余地がある (例: schema が prose body 型を宣言してあればアクセス時に自動処理)。本タスクの最低線は明示適用で、暗黙適用は別タスクとして切り出す。

### インラインコードのフェンス長 (O4)

> **未実装** — Phase 10 タスク [O4](../../../tasks.md)。

内蔵テンプレート（`__meta_entity` の attributes 表など）は、`metadata` / `validation` のような任意 Mapping を Markdown テーブルセルに `{{ value | to_yaml(true) }}` でダンプし、結果をインラインコードとして表示している。現在は単一バッククォートで囲んでいるが、値そのものにバッククォートが含まれると CommonMark のフェンスが内側で早期終了してセルが崩れる。

例: 値の中に `` `text/markdown` `` が含まれていると、

```
`always `text/markdown` ...`
```

の 2 番目のバッククォートが終端と解釈され、`text/markdown` がコード表示から外れる。

CommonMark の規定どおり、**値に出てくる連続バッククォートの最長 + 1** の長さでフェンスを動的に決める `code_fence` フィルタを導入してテンプレートから呼ぶ:

- 値にバッククォートを含まない → `` ` `` で囲む
- 1 個含む → `` `` `` で囲む
- 2 連続含む → ` ``` ` で囲む

値の先頭/末尾がバッククォートのときは内側に半角スペースを足す（CommonMark の規定。`` ` ` ` `` のように単独のバッククォートを表示するため）。
