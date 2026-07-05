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
- 主題が `this` でノードとして取れることはリンク解決の足場でもある — source ページ（主題ノード）を `this` から得られるので、resolver は per-render の source-node 束縛を持たず静的な `(Edition, node_map)` だけを束縛すればよい（[generator.md のリンク解決](10-generator.md#リンク解決)）。
- スカラ主題を**分割時のみ**エラーにするのは、ページはアンカーパスを持つノードであるべきだから（inline 展開は単なる差し込みなので任意の値を許す）。

### 分割ルール

`{% mood_view %}` が主題の `_meta.object_type_id` を `file_per` と照合して分割/インラインを決めること、親ページのリンクは mood_view が自動生成せず author が `| link` で書く two-loop パターン（分割なら別ページ URL・インラインなら同ページ `#fragment` に自動適応）は `docs/reference/template.md` の Split vs inline を正本とする。設計判断:

> **背景: なぜ自動リンクを mood_view に持たせないか.** 当初案は「分割時に親へリンクを残す」だったが、リンク解決の責務は既に `| link` ＋ page_path にあり、しかも分割/インラインへ自動適応する。mood_view にリンク生成を畳み込むと二重実装になり、かつ親側の周辺マークアップ（リスト記号・付随情報）を author が制御できなくなる。mood_view の責務は「このノードの内容をどこに置くか」の一点に保つ。`{% mood_view %}` にブロック本体やアーム（`{% split %}` 等の発明語）を持たせる糖衣も検討したが、two-loop パターンが既知の素の構文だけで同じことを達成するため採らない。

> **背景: per-call-site インライン上書きは持たない（`inline` キーワードを廃止）.** 旧 `{% mood_view ... inline %}` は file_per 機構導入前の唯一のインライン手段だったが、file_per 導入後はインライン意図を **型単位ポリシー（file_per から外す）**で表現でき、call-site 上書きとの併存は footgun を生んだ: file_per 対象の型を call-site で `inline` 強制すると、そのノードが「自前ページ」と「インライン本文」に**二重出力**され、`| link` の指す先と内容の所在がずれる。よってインラインは型単位の一手段に統一した。将来 per-instance 需要が出たら別機構で入れ直す。

> **見出し深さ.** subtemplate が「見出し＋本文」を一単位で再利用したいとき、埋め込み先によって見出しレベルが変わる（同じ型を `##` 下でも `###` 下でも置きたい）。この深さ調整は mood_view 固有ではなく、生成側の `under_heading` フィルタ（任意の埋め込み出力をブロックで囲む／prose body をパイプで処理）が担う。split 時に mood_view が `""` を返す性質と合わさり、同じ記述が分割でもインラインでも正しく出る。仕様は `docs/reference/template.md` の `under_heading` を参照。

### ページパスと出力ディレクトリ

ページパスの導出規則（anchor_path 由来、root は `index.md`、セグメントは anchor_path と同じ IRI エスケープを継承）は `Edition.page_path` が持ち、正本は [generator.md](10-generator.md#ページパスの導出)。`page_path` は **edition ルート相対**で、実ファイルは mood_view が edition のマウント先を被せた `{outDir}/{edition}/{page_path}` に書き出す（form A は暗黙 edition `default`）。各 edition ディレクトリと診断系出力（`index.md`、`__entity_defs/` 等）は `{outDir}` 直下に横並びになる:

```
{outDir}/
  index.md                                     ← メタ index（入口。各 edition を列挙）
  default/   (form B なら web/ print/)          ← edition（report 本体）
  __entity_defs/  __entity_data/  __queries/   ← 診断（edition 横断・常に同位置）
```

診断系は `__` 予約済みなので edition 名と衝突せず、edition 横断で常に同じ位置に出る。

> **背景: リンク層を触らずに済む.** リンク URL は page 相対（`node_href` は source ページから target ページへの relpath、[generator.md のリンク解決](10-generator.md#リンク解決)）なので、`{edition}/` のマウント接頭辞はリンク解決に対して透過。各 edition が自分の `file_per`（→自分の `page_path`）で解いた相対 URL がそのまま正しく、リンクフィルタ層に改修は要らない。各 edition は自己完結した相対リンクのサブツリーになる。

## Internal Design

### meta 診断の分割

meta 診断ページ（`__entity_defs` / `__entity_data` / `__queries`）の主題は **実データツリーノード**で、専用のビルトインクエリ（`src/another_mood/resources/queries/`）が生む。`{% mood_view %}` の分割判定は一様で、[分割ルール](#分割ルール)そのもの — **主題が実ノードかつ `object_type_id` が file_per 対象なら分割、それ以外はインライン**（予約マーカーも template-keyed fallback も無い）。

主題ノードを生む 3 クエリ:

- `__entity_defs` / `__entity_data` — どちらも `from: __definition.entities`（`view: false`・ルート entity）で**同じ entity 集合**を引くが、**別クエリ＝別アンカールート**（`/__entity_defs/{id}` と `/__entity_data/{id}`）。同一 entity を Definition と Data の **2 ページ**に出すのに、クエリ名でアンカーを分けることで one-node-two-pages 衝突を避ける（差は select のみ: 前者 `id`+`builtin`、後者 `id`）。
- `__queries` — `__definition.queries` の passthrough（`select` 省略）。各アイテムが query 定義の全フィールドを持ち、テンプレートがそのまま描画する。

meta レンダリングには利用者の `reports.yaml` が無いので、分割は **固定の内部 file_per**（`meta_templates.META_EDITION` = `__entity_defs.item` / `__entity_data.item` / `__queries.item`）で駆動する。各結果アイテムの anchor_path `/{view}/{id}` から通常の page_path 規則で `{view}/{id}.md` が導かれる — **1 ノード 1 ページ**。共有コンテキストである data root と schema は、子テンプレが anchor_path で直接引く（root = `node("/")`、schema = `node("/__definition/entities")`。`node` は anchor_path→node 解決の global で、`build_node_map` が全 wrap ノードを anchor_path で索けるようにするため成り立つ）ので、主題ノードは identity フィールドだけを持てばよい。

> **背景: 別ページが要るならノードを一つ立てる.** 旧実装は `__root.md` 内で合成 dict（アンカーパス無し）を組み、予約キー `_split` ＋ template-keyed fallback（`{template_stem}/{id}.md`）で分割していた。これは「1 ノード→複数ページ」を fallback がテンプレート名で曖昧性を割る誤魔化しで、**one-node-one-page ポリシー違反**だった。別ページが要るならノードを一つ立てる — 同一 entity に 2 ページ要るなら `__entity_defs` と `__entity_data` の 2 ノードを立てる、というのがこの原則の実践で、`_split` マーカーと fallback は撤去された。

> **残: `__db/` への移動（F9）.** これら `__{view}/` は今も output 直下に横並びで散る。集約は meta-edition の `name` を `__db` に倒して `{out_dir}/__db/__{view}/` へマウントする形で行う（[Proposals](#proposals) 参照。前提の render ループ一般化は C12 で完了済み）。

### render ループ

`generate()` は `(META_EDITION, *user_editions)` を回す**単一ループ**で全 edition を出す。メタ edition もユーザ edition も同じ `Edition` 型 —「差分フィールドを持つ heterogeneous な edition kind」で、`templates_dir` / `root_template` / `file_per` / `dir_segment`（`name` 由来）/ `extra_filters` だけが違う。ループはこれらを edition から読んで `render()` するだけで、メタ描画を特別扱いする分岐を持たない。

- **メタ edition は root マウント**（`name=""` → `dir_segment=""` なので `out_dir / "" == out_dir`）で、出力は 2 経路時代とバイト単位で不変。ユーザ edition は `{out_dir}/{dir_segment}/`。メタは専用のビルトインテンプレ（`META_TEMPLATES_DIR`）と system-only の `extra_filters`（`pluck` / `to_yaml` / `walk_entity`）を持ち、これらはユーザレンダーには載らない。
- **`root_template` は当面 `index.md` 固定**。この差分フィールドが「[Edition 別ルートテンプレート（将来）](#edition-別ルートテンプレート将来)」の継ぎ目で、利用者が `reports.yaml` で別テンプレを指定する余地を機構として既に持つ。
- 各フィールドの意味と背景は `Edition` / `META_EDITION` の docstring、ループ本体は `generator.generate()` を正本とする。

### メタ index の edition 列挙

メタ index（`{outDir}/index.md`）の `## Reports` は各 edition を名前でリンクする（form A は `[default](default/)`）。edition の列は generator がモデルの最上位 `__` メタチャネルに `__editions` として注入し（`__definition` 等と同経路で、ルート直下の配列ノード `/__editions` になる）、各要素は `{name, segment}` レコード — `name` は表示ラベル（raw）、`segment` は出力／リンク用の IRI エスケープ済みセグメント（`Edition.dir_segment`）。テンプレートは `{% for e in __editions %}` で反復し `[{{ e.name }}]({{ e.segment | safe }}/)` を出す（href は escape 済みなので `| safe` で finalize の md エスケープを回避）。出力ディレクトリ（`{outDir}/{segment}/`）と href が同一の `segment` を共有するので常に一致する。ASCII-safe 名は raw とエスケープ後が一致するため、通常は表示と URL が見分けつかない。global 配線も `reports.yaml` 依存も持たず、form B で edition が増えても列が伸びるだけでテンプレ無改修。edition 横断の landing ページは作らず、入口はメタ index に集約する。

`__editions` に載るのは**ユーザ edition だけ**で、同じ [render ループ](#render-ループ)が回すメタ edition は含めない — 「ループが回す edition 群」と「トップが宣伝する `__editions`」を別チャネルに保つことで、メタを内部的には edition の一種としつつ利用者向けには出さない。この分離は F9 の表紙（deliverable と DB 自己記述を別軸に置く）が乗る土台でもある。

## Proposals

診断サーフェスの再配置とトップページの再設計（F9）。内部の一般化 — メタ描画とユーザ edition の 2 経路を単一 render ループへ畳む振る舞い不変リファクタ — は C12 で完了済み（[render ループ](#render-ループ)）。残るは利用者向けの移動＋表紙。既存の editions (form B) の設定・制約は [External Design](#レポート設定ファイル)、メタ index の列挙は [Internal Design](#メタ-index-の-edition-列挙) を正本とする。`Edition` ドメイン型・`load_editions` の form A/B 分岐・`dir_segment`・`generate()` の render ループは `edition.py` / `generator.py` の docstring を参照。

### システムメタの `__db` 移動と表紙 (F9)

C12 の抽象化に乗る利用者向けの変更。

- meta-edition の `name` を `""` → **`__db`** に倒す。これだけで meta サーフェス一式が `{out_dir}/__db/` 配下へ移る（index → `__db/index.md`、split 子 → `__db/__entity_defs/{id}.md`）。root マウントを剥がしたぶん root が空くので、次項の表紙で埋める。
- **二段の `__` はどちらも落とせない.** マウント `__db`（edition 名のユーザ空間との衝突回避）と各アンカールート `__entity_defs`（グローバル node_map でのユーザ entity/query 名との衝突回避）は **別レイヤの別事情**で `__` 始まりを要求する。ゆえに `__db/entity_defs` にはできず `__db/__entity_defs`（[予約プレフィックス](../40-json-data-model.md#予約プレフィックス)）。単一 `__` の `__db/entity_defs` にする唯一の道は `__db` を本物のアンカー親にして meta 各ビューをその子ノードに入れ子化することだが、データツリーの構造改組で重く、採らない。
- **root に二セクションの薄い表紙テンプレ**を新設する: `## User Reports`（各 edition を大々的に列挙）＋ `## Database Information`（`__db/` へ控えめにリンク）。C12 が用意した edition kind 機構（`Edition` の `root_template` / `templates_dir` / `extra_filters` ＋ 統一ループ）に、root ページを持つ cover edition（`name=""`・専用テンプレ・`file_per` なし）を新設して `[cover, meta(__db), *user]` の先頭に据える形で乗る。edition 列挙（現 `## Reports`）は meta index からこの表紙へ移す。

> **背景: なぜ診断を `__db/` へ退避しつつ表紙で一級に見せるか.** 現トップは ER 図・entity 一覧・query 一覧をインライン展開した診断本体で、著者の成果物は末尾 `## Reports` の目立たない `[default]` リンクに埋もれている — scaffolding（DB の自己記述）が deliverable（著者のレポート）を押しのける倒錯。かといって診断を無差別なリンク集にフラット化すると、MS Access の「データベースウィンドウ」に当たる自己記述面が「体裁違いのレポートの一種」に誤ラベルされ、source-based database のアイデンティティが玄関で不可視になる。よって **出力の種類（deliverable / データベースの自己記述）で二分**し、表紙で deliverable を前面に、DB 探索面（`__db/`）を控えめだが一級の別エントリとして示す。診断は edition 軸には混ぜない（内部実装上は edition の一種でも、利用者向けには別軸）。

> **波及（着手時に同期）.** `docs/guides.md` と `docs/reference/reports.md` の `output/__entity_defs/…` 表記 → `output/__db/__entity_defs/…`、Quick Start、`__warnings/` の置き場と reconcile が `## Warnings` を append する先。

### Edition 別ルートテンプレート（将来）

edition ごとに異なるルートテンプレート（`index.md` 以外）を**利用者が `reports.yaml` で指定したい**需要（Web 版と印刷版でトップ構成を変える等）。**機構（`Edition` の `root_template` / `templates_dir` フィールドと `generate()` ループでの差し替え）は C12 で入った**ので、残るは reports.yaml への設定露出（`root_template` エントリのパースと `load_editions` での反映）のみ。加算的拡張で、F9 のスコープからも外す。
