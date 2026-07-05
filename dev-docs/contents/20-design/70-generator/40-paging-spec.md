# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割と edition の出し分けを定義する。

## External Design

### レポート設定ファイル

設定構文（form A の `file_per`、form B の `editions:` マップ、edition 名規則、`oneOf` 検証）は `docs/reference/reports.md` を正本とする。設計判断:

- **edition は同一 report の体裁違いの並行出力**で、当面の差は `file_per`（分割粒度）のみ。Markdown→HTML レンダリングは全 edition 同一で、別レンダラ・別フォーマットは持たない。
- 全 edition を 1 ビルドで横並び公開する — **環境で 1 つ選ぶ "profile" ではない**。"並列ビルド" は成果物が横並びに出る意で concurrency は持たず、単一 edition 選択（`--edition`）も当面持たない。
- form A は暗黙の単一 edition `default`。edition 名の検証は**ゆるく**（非空・最低 1 件・`__` 始まり禁止）に留め、出力セグメント化時に anchor_path と同じ IRI エスケープ（`Edition.dir_segment`、表示は raw のまま）で FS-safe にする。FS 固有のキツいエッジ（長さ・予約名等）は C7 に委ねる。

### テンプレート主題のノード受け取りと `this` 束縛

主題（subject）を `this` でどう参照するか（Mapping の spread／`this`／Array 反復、スカラ値の扱い）は `docs/reference/template.md` の Subtemplate side を正本とする。設計判断:

- **束縛はレンダリング境界（`template_engine._bind`）の単一規則**として root テンプレート（`index.md`）と `{% mood_view %}` サブテンプレートに同一適用する。利用者から見えるデータモデルがツリー全体で一致し、root も自ノードを `this` で参照できる。`{% mood_view %}` 側はパス決定とノードのパススルーだけを担い、context 構築を持たない。
- 主題が `this` でノードとして取れることはリンク解決の足場でもある — source ページ（主題ノード）を `this` から得られるので、resolver は per-render の source-node 束縛を持たず静的な `(PagingPolicy, node_map)` だけを束縛すればよい（[generator.md のリンク解決](10-generator.md#リンク解決)）。
- スカラ主題を**分割時のみ**エラーにするのは、ページはアンカーパスを持つノードであるべきだから（inline 展開は単なる差し込みなので任意の値を許す）。

### 分割ルール

`{% mood_view %}` が主題の `_meta.object_type_id` を `file_per` と照合して分割/インラインを決めること、親ページのリンクは mood_view が自動生成せず author が `| link` で書く two-loop パターン（分割なら別ページ URL・インラインなら同ページ `#fragment` に自動適応）は `docs/reference/template.md` の Split vs inline を正本とする。設計判断:

> **決定: 親リンクを mood_view に畳み込まない.** リンク解決は既に `| link` ＋ page_path が持ち分割/インラインへ自動適応するので、mood_view に持たせると二重実装になり、親側の周辺マークアップ（リスト記号等）も author の制御外になる。mood_view の責務は「このノードの内容をどこに置くか」に保つ。

> **決定: インラインは型単位ポリシー（call-site 上書きは持たない）.** インライン意図は型を `file_per` から外して表現する。file_per 対象の型を call-site で `inline` 強制すると、そのノードが自前ページとインライン本文に**二重出力**され、`| link` の指す先と実体の所在がずれる（footgun）。

> **見出し深さ.** subtemplate が「見出し＋本文」を一単位で再利用したいとき、埋め込み先によって見出しレベルが変わる（同じ型を `##` 下でも `###` 下でも置きたい）。この深さ調整は mood_view 固有ではなく、生成側の `under_heading` フィルタ（任意の埋め込み出力をブロックで囲む／prose body をパイプで処理）が担う。split 時に mood_view が `""` を返す性質と合わさり、同じ記述が分割でもインラインでも正しく出る。仕様は `docs/reference/template.md` の `under_heading` を参照。

### ページパスと出力ディレクトリ

ページパスの導出規則（anchor_path 由来、root は `index.md`、セグメントは anchor_path と同じ IRI エスケープを継承）は `PagingPolicy.page_path` が持ち、正本は [generator.md](10-generator.md#ページパスの導出)。`page_path` は **edition ルート相対**で、実ファイルは mood_view が edition のマウント先を被せた `{outDir}/{edition}/{page_path}` に書き出す（form A は暗黙 edition `default`）。root の入口には薄い**表紙**（cover。edition ではなく一回 render）を置き、システム生成のメタ（DB の自己記述）は `__db/` マウントへ退避する:

```
{outDir}/
  index.md                                     ← 表紙（cover。H1=project 名 / Reports + Database Information）
  default/   (form B なら web/ print/)          ← ユーザ edition（report 本体）
  __db/                                        ← DB 自己記述（メタ edition のマウント先）
    index.md                                     メタ index（ER 図・entity/query 一覧）
    __entity_defs/  __entity_data/  __queries/   診断（edition 横断・常に __db 内の同位置）
```

`__db` マウントと各アンカールート（`__entity_defs` 等）はどちらも `__` 始まりだが要求する事情は別レイヤ: `__db` は edition 名のユーザ空間（`__` 始まりは検証で禁止）との衝突回避、`__entity_defs` はグローバル node_map でのユーザ entity/query 名との衝突回避。ゆえに `__db/entity_defs` にはできず `__db/__entity_defs` になる（[予約プレフィックス](../40-json-data-model.md#予約プレフィックス)）。診断系は `__db` 内で edition 横断・常に同位置。

出力は **deliverable（著者の reports）と DB 自己記述（`__db/`）の 2 種**で捉え、表紙で reports を前面・`__db/` を控えめな別エントリに置く。`__db/` を reports / edition の軸には混ぜない（自己記述面を「体裁違いのレポート」に誤ラベルさせないため）。`__warnings/`（reconcile の警告ページ）は build-report 層で自己記述とは別軸ゆえ `{outDir}/__warnings/` 直下、リンクは表紙 `index.md` に append。

マウントはリンク解決に**透過**: リンク URL は page 相対（`node_href`）なので `{edition}/` や `__db/` のマウント接頭辞は効かず、各 edition / マウントは自己完結した相対リンクのサブツリーになる（[generator.md のリンク解決](10-generator.md#リンク解決)）。

## Internal Design

### meta 診断の分割

meta 診断ページ（`__entity_defs` / `__entity_data` / `__queries`）の主題は **実データツリーノード**（`resources/queries/` のビルトインクエリが生む）で、分割は通常の[分割ルール](#分割ルール)そのもの。meta には利用者の `reports.yaml` が無いので paging は固定（`META_EDITION.paging`）。

> **決定: 別ページが要るならノードを一つ立てる.** 1 ノードは（データ位置で定まる）1 ページにだけ描かれる。同一 entity を Definition と Data の 2 ページに出すのに `__entity_defs` / `__entity_data` の **2 クエリ＝2 アンカールート**を立てるのがこの実践 — 予約キーや fallback で 1 ノードを複数ページに割る手は採らない。

### render ループ

`generate()` は 2 サーフェスを出す:

- **表紙**（`{outDir}/index.md`）— deliverable を列挙する root ランディング。**データモデルを描かない**単発 render（edition ではなく、reconcile の build-report ページと同類）なのでデータ edition ループの外。
- **データ edition**（メタ=`__db/` + ユーザ）— データモデルを描く。メタもユーザも同じ `Edition` 型なので**単一ループ**で回し、メタを特別扱いする分岐を持たない。

各 `Edition` の差分フィールド（`paging` / `templates_dir` / `root_template` / `dir_segment` / `extra_filters`）と render 本体は `edition.py` / `generator.generate()` の docstring が正本。`root_template` は当面 `index.md` 固定で、[Edition 別ルートテンプレート（将来）](#edition-別ルートテンプレート将来)の継ぎ目。

### 表紙の edition 列挙

表紙はデータループと**同じ `editions` 集合**を受け取り、`Edition.is_system` で 2 セクションへ振り分ける。決定:

- **H1 は project 名**（`project_dir` の basename）。
- `## Reports` = 非 system（ユーザ edition）を列挙、`## Database Information` = system（メタ edition）へ 1 本リンク。
- `## Database Information` のリンク先は**メタ edition の `dir_segment` から導出**（`__db/` を直書きしない）ので、マウント名を変えても追従する。
- 着地する `__db/index.md` の H1 は固定 `# Database Information` — 表紙の同名セクションから同名ページへ着く導線を保ち、project 名依存を表紙 1 箇所に閉じ込める。

## Proposals

### Edition 別ルートテンプレート（将来）

edition ごとに異なるルートテンプレート（`index.md` 以外）を**利用者が `reports.yaml` で指定したい**需要（Web 版と印刷版でトップ構成を変える等）。**機構（`Edition` の `root_template` / `templates_dir` フィールドと `generate()` ループでの差し替え）は C12 で入った**ので、残るは reports.yaml への設定露出（`root_template` エントリのパースと `load_editions` での反映）のみ。加算的拡張で、F9 のスコープからも外す。
