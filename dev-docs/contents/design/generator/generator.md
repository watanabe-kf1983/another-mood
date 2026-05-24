# Document Generator

## Internal Design

### 内蔵ルートテンプレート

Generator はユーザの `index.md` テンプレートを直接エントリポイントとせず、内蔵のルートテンプレートを起点とする。ルートテンプレートは以下の 2 セクションを持つ:

1. **メタドキュメンテーション** — 内蔵テンプレートでスキーマ・クエリを可視化（[meta-documentation.md](../app/meta-documentation.md) 参照）
2. **ユーザドキュメント** — ユーザの `index.md` テンプレートを呼び出す

これにより、メタドキュメンテーション・ユーザドキュメントが同じテンプレートシステム上で動作する。

### パーシャルテンプレートとエスケープ

パーシャル単位で出力フォーマットが決まり、拡張子でエスケープモードを判定する:

| 拡張子 | エスケープモード |
|---|---|
| `.md` | Markdown エスケープ |
| `.mermaid` | Mermaid エスケープ |

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

### ノードメタデータ (B1)

> **未実装** — Phase 11 タスク [B1](../../../tasks.md)。

データツリー上のノード (Mapping / Array) に、テンプレートからアクセスできるシステム由来のフィールドを注入する。テンプレートは元データを「ちょっと拡張された dict / array」として直接走査する。

#### 公開フィールド

| フィールド | 対象ノード | 内容 |
|---|---|---|
| `_parent` | 全ノード | データツリー上の直近の親ノード。Array 要素なら Array、Array なら親 Mapping、Mapping なら親 Mapping。root では未定義 |
| `_parent_record` | Mapping のみ | 最も近い Mapping 祖先。Array 要素から見て Array を 1 段飛ばして親 Mapping を返す。Mapping 自身が dict 直下のキーなら `_parent` と同じ |
| `_meta.anchor_id` | 全ノード | このノードのアンカー ID 文字列 ([anchor-spec.md](anchor-spec.md) の規則に従う) |
| `_meta.object_type_id` | 全ノード | このノードのスキーマ位置を表す path 形 ID。Mapping は ObjectType ID (`X.item`)、Array は field path 形 (`X.item.yyy`、catalog 表記 `X.item.yyy.item[]` の同義) |
| `_meta.page_url` | 全ノード | 表示先 URL。paginate 設定 ([paging-spec.md](paging-spec.md)) を参照し、自身が分割対象なら自ページ、でなければ親側を遡って解決。lazy 評価可 |

対象範囲: anchor ID 付与可能な Mapping / Array ノード全て (= anchor-spec の規則で path target になり得る全ノード)。

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
{{ task._meta.anchor_id }}          {# 例: "categories/G/tasks/G1" #}
{{ task._meta.page_url }}           {# 例: "categories/G.md" #}
```

#### 背景: parent の二系統セマンティクス

データツリー上の親参照は、利用文脈に応じて自然な意味が二通りある:

- **直近の親ノード** (`_parent`): ツリーの直近上位ノードへのエッジ。Array 要素から見れば Array、Array から見れば親 Mapping。データツリーの構造を素直に反映
- **最も近い Mapping 祖先** (`_parent_record`): 子要素から「自分が属するレコード」を取得する場面で自然。Array 要素 → 親 Mapping が 1 hop で書ける

両系統を明示的に提供することで「親」の意味を読み手・書き手の双方が誤読しないようにする。

#### 仮仕様

- 付与タイミング: Generator のデータロード時 (フィールド評価は lazy 可)
- 対象: anchor ID 付与可能な全 Mapping / Array ノード
- 命名: `_parent` / `_parent_record` / `_meta` の 3 つを top-level の `_` 予約プレフィックス枠に置く
- スコープ: Generator 内部のみ。preprocess / composer の出力データには現れない
- `_meta.object_type_id` の公開度: 内部的に `_meta.page_url` 算出に必要なので保持するが、テンプレ API としての利用者公開の必要性は当面薄い (現時点では公開してよいが、設計上は内部利用優先)

### リンク解決 (B2-B6)

> **未実装** — Phase 11 タスク [B2〜B6](../../../tasks.md)。アンカーの仕様 (リンク記法 / フィルタ API / 解決のタイミング) は [anchor-spec.md](anchor-spec.md) を参照。

リンク解決は pre-render 段階で完結する (post-render の文字列置換は採らない)。各テンプレート render 用の TemplateEngine インスタンスに対し、resolver を closure binding で渡し、各種フィルタが共有する。

#### resolver 内部 (B3)

anchor ID からノードへの解決機構:

1. anchor ID でデータツリーを走査し、最初にヒットしたノードを返す
2. ヒットしたらキャッシュ (anchor_id → ノード) に登録
3. 2 回目以降は O(1) で解決
4. ノードの `_meta.page_url` + フラグメント (`#<anchor_id>`) でリンク URL を生成

走査は `/` 区切りのセグメント単位で進めるが、先頭セグメントが `prose` のときは残り全体を 1 つの id として扱う ([anchor-spec.md](anchor-spec.md#prose-の例外) 参照)。

全ノードの事前インデックスは構築しない。リンク対象は主要オブジェクトのごく一部であり、オンデマンド走査 + キャッシュで十分。

#### anchor フィルタ (B4)

テンプレート内で anchor ID から `[<display>](<URL>)` / display 文字列 / URL 文字列 を生成する 3 つのフィルタ:

- `anchor_link(anchor_id, [override_text])` — Markdown リンク全体
- `anchor_title(anchor_id)` — display text のみ (`title` → `name` → `id` → anchor_id 全体 のチェイン)
- `anchor_url(anchor_id)` — URL のみ

仕様は [anchor-spec.md](anchor-spec.md#リンク記法) を参照。

#### prose body 処理フィルタ (B5)

Markdown データソースの body には、Normalizer がソース内の相対リンクを `toc:` 記法に変換済みのリンクが含まれる ([markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照)。仮称 `resolve` フィルタが body 内の `toc:` URL を実 URL に置換する。

このフィルタは anchor 解決以外にも、見出しレベル正規化やエスケープ調整等の prose body 固有処理を兼ねる総合処理フィルタとして位置付ける (具体仕様は別途)。

##### 暗黙適用は別途検討

`{{ prose.body | resolve }}` を author に書かせるか、システムが自動的に処理を挟むかは、ノードメタデータ機構 (B1) の延長で検討する余地がある (例: schema が prose body 型を宣言してあればアクセス時に自動処理)。本タスクの最低線は明示適用で、暗黙適用は別タスクとして切り出す。

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
