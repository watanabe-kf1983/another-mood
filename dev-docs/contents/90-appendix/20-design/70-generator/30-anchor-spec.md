# Anchor Specification (appendix)

[Anchor Specification](../../../20-design/70-generator/30-anchor-spec.md) の背景と精密な規則。

## なぜリゾルバを `node()` と呼ぶか

`link` / `label` / `href` は「ノードを受けて、そのノードの何かを描画する」フィルタ族で、アンカーターゲット (`<a id>`) を描画するフィルタの自然な名前は `data | anchor` — `<a id>` / `<a href>` の両面が `anchor` / `href` という対の名前で揃う。そこで anchor の語は HTML 本来の意味（受け側の標識）に予約し、リゾルバは「アンカーパスを解決して得られるもの」の名 — ノード — で `node()` とした。node / data tree は利用者向けリファレンス (`docs/reference/template.md` の Anchor paths 節) が先行して採用していた語彙でもある。

## view の一意性を保証しない理由

view については一意性を保証できず、保証を強制すべきでもない。`flatten` は 1 行を N 行に割るので、親の id を `select` に残せば必ず重複する（`showcase/music` の `artist_album_pairs` が意図された用法のままこの形になる）。一方 1:1 射影の view は正当なアンカーパスを持つため、view 単位でも判別できない。したがって検出は identity が実際に消費される時点まで遅らせ、ページ主語として描画されたときに出力パスの衝突（`PageCollisionError`）としてのみエラーにする（[一意性](../../../20-design/70-generator/30-anchor-spec.md#一意性)）。inline に描かれた重複はノードマップの後勝ちのまま検出されない。

## Escape 規則の精密な条件

id 値が `/` を含む場合の `%2F` 以外の文字は **IRI エスケープ**で正規化する:

- **生のまま残す**: ASCII の unreserved (`A–Za–z0–9-._~`) と、**非 ASCII の `ucschar`**（RFC 3987 が IRI で許す Unicode 範囲。漢字・かな・非 ASCII 句読点・記号等。例: `書籍`、`モーニング娘。` の `。`、`藤岡弘、` の `、`）
- **percent-encode する**: ASCII の予約・特殊文字（空白 → `%20`、`# ? : * | \ " < >` 等）と、`ucschar` 外の非 ASCII（制御・surrogate・private-use・noncharacter）

つまりエスケープは「URI-encode から `ucschar` を除いた IRI 形」。アンカーパスは URL（fragment・リンク先）と `<a id>` に埋め込まれる住所で、IRI 形にすることで「人が読める住所（`/prose/書籍`）」と「URL として正当」を同時に満たす。URI への直列化（`書籍`→`%E6%9B%B8%E7%B1%8D`）は消費側（Hugo の Goldmark・ブラウザ・静的サーバ）が行う（リンクの着地に要る `<a id>` の描画は別問題で Hugo の raw HTML 許可を要する — [アンカーの発行](../../../20-design/70-generator/30-anchor-spec.md#アンカーの発行)を参照）。

エスケープは **encode 片道**で、生の segment/id 値に 1 回だけ適用する（既存の `%XX` を decode・二重 encode しない。`%` 自体は ASCII 特殊文字なので `%25` に encode される）。

なお id value（データ側セグメント）は無制約だが、attr name（構造側セグメント）はスキーマの `^[\p{L}_][\p{L}\p{M}\p{N}_]*$` で識別子状に制約済みで、ucschar/unreserved を素通りする。

`ucschar`（RFC 3987）のレンジは `shared/url.py` の `_UCSCHAR_RANGES` が持つ（サロゲート・noncharacter・private-use を除外）。

### なぜ IRI 形か

エスケープは全非 ASCII を percent-encode せず、生 Unicode を残す **IRI 形**にする。`書籍`→`%E6…` では `node:/prose/…` の住所も `<a id>` も読めなくなるため。IRI ⇄ URI は同一資源の別表現で、生 Unicode のリンク/ファイル名も CommonMark・HTML/URL 標準上正当なので生で残して問題ない。keep-raw 集合はカテゴリ（`\p{L}\p{N}`）でなく `ucschar`（レンジ）— `モーニング娘。`「藤岡弘、」のように **実在 id が非 ASCII 句読点を含む**ため。

## Prose / Blob の例外の理由

組み込みの `prose` / `blob` entity に限り id 内の `/` を素通しにする理由:

- `prose` / `blob` の id は contents/ 内ファイルの相対パスから生成され（prose は拡張子を落とし、blob は残す）、構造的にパス階層を持つ。これを `%2F` でエンコードすると `prose/design%2Farchitecture`・`blob/covers%2Fcover.png` のような可読性の低い文字列になる。加えて、blob 参照は `node:/blob/<id>` の形で相対リンクから導出される（[prose-spec.md の content](../../../20-design/50-normalizer/25-prose-spec.md#content--ソースそのまま相対リンクだけ-node-化)）ため、著者が素の `/` で綴る参照とアンカーパスのキーを一致させる必要がある
- `prose` / `blob` はいずれも flat な配列 entity で sub-entity を持たないため、resolver が `prose/`・`blob/` 以降を「単一の id」として扱えば曖昧性は発生しない

id 形がシステム側で固定されている（contents 相対パス）ため将来も曖昧性は生じない。一方、`/` を含む任意の id への一般化はしない — 利用者 entity は構造が変わりうるため、その id を素通しにすると将来曖昧性が混入する。

見出しを `<prose レコードの anchor_path>#<github-slug>` に畳む形について: `#` は `/` と同様に raw で挿入する構造的セパレータ。slug は github 互換で `#` を含まず、id 内の `#` は `%23` に escape されるため、anchor_path 中のリテラル `#` は見出し区切りの一個だけ。「`prose/` 以降は単一 id」の前提も、`#` の手前までを単一 id と読み替えることでそのまま保たれ、`/`-曖昧性は生じない。

## アンカーパスの例

正規化後の views データ:

```yaml
overview:                          # オブジェクト → singleton
  title: システム概要

erds:                              # 配列 → リスト
  - id: user-management
    title: ユーザー管理の ER図
    entities:                      # 配列 → リスト（ネスト）
      - id: user
        title: ユーザー
      - id: account
        title: アカウント
  - id: order-flow
    title: 受注フローの ER図
    entities:
      - id: user                   # 別の erd 配下なので user-management.entities.user とは別物
        title: ユーザー（注文視点）

prose:                             # flat list、id はファイル相対パス
  - id: design/architecture
    title: Architecture
    headings:                      # 本文見出し（prose-spec.md の headings）
      - { id: エラー処理, title: エラー処理, level: 2 }
blob:                              # flat list、id は拡張子込みファイル相対パス
  - id: covers/cover.png
    mime_type: image/png
```

| アンカーパス | 指す対象 |
|---|---|
| `/` | root（views 全体） |
| `/overview` | overview singleton |
| `/erds/user-management` | user-management の ER図 |
| `/erds/user-management/entities/user` | user-management 配下の user エンティティ |
| `/erds/order-flow/entities/user` | order-flow 配下の user エンティティ（衝突しない） |
| `/prose/design/architecture` | Architecture 散文（id 内 `/` を素通し） |
| `/prose/design/architecture#エラー処理` | Architecture 本文中の見出し（`headings` セグメントは畳む） |
| `/blob/covers/cover.png` | cover.png への blob 参照（id 内 `/` を素通し、拡張子込み） |

アンカーパスは **データツリー上の到達経路そのもの** で構成されるため、ネストしたリスト要素間で id が重複してもアンカーパスは衝突しない。

## 未解決参照に素テキストでなく角括弧を残す理由

リンクを外して素テキストにすると解決成功時の通常テキストと見分けがつかず、失敗が出力に埋もれる。`[text]` は対応する参照定義を持たない shortcut reference として CommonMark が角括弧ごとそのまま描画するため、壊れた参照が目立つ。表示テキストは常に残るので author は気づいて直せる。当初は `link` を素テキスト・`relink` を `[text]` と割っていたが、両者を `[text]` に統一した。

## `anchor_path` フィルタを公開から外した経緯

アンカーパス文字列だけを返す公開フィルタは置かない。当初 `anchor_path(seg, *segs)` として公開していたが実需が一度も現れず、組み立ては `node()` が担っているため公開名から外した。`anchor_path` の名は現在、ノードから文字列を取り出すメタテンプレート専用フィルタが使う（[ノードメタデータ](../../../20-design/70-generator/30-anchor-spec.md#ノードメタデータ)）。

## scheme 名を `node:` とする背景

リンク先の実体をテンプレートでは `node()` で解決する。本文側の scheme も同じ語に揃え、`[x](node:/…)` ↔ `node(path="/…") | link` を一目で対応づけられるようにする。`anchor` は受け側（`<a id>`）に予約済みなので scheme には使わない。`node:` は実在 URI スキームと衝突しない。アンカーパス参照以外の内部 URL を将来挟む場合は、傘名前空間（`mood:` 等）でなく種類ごとに別 scheme を立てる方針。

## なぜメタデータをテンプレートから直接触らせないか

テンプレートエンジン (minijinja) は `_` 始まりの **Python 属性**を undefined にし、メソッド呼び出しは拒否する（データ側の `_` 始まりキーは通る）。`row["_meta"]` も `attr()` も同じく undefined になるので迂回路は無い。これはホスト側の内部にテンプレートを触らせないという信頼モデルの意図そのもので、押し戻す理由がない。

かといって prefix を外して `meta` 等にはしない。ノードは dict / list のサブクラスで、テンプレートからの `row.meta` は getitem を先に引くため、データ側に `meta` キーがあると静かにそちらが勝つ。`_` prefix はまさにこの shadowing を防ぐためにあり、Python 側では load-bearing なまま残す。したがって prefix は据え置き、**テンプレートへの出口だけをフィルタに移す**。

実際の消費者はこれで足りる: テンプレートからの実需はメタテンプレートの診断テーブルが描くアンカーパス列 1 箇所だけで、それはメタテンプレート専用フィルタ `anchor_path`（ノード → 文字列）が担う。残りの `_parent` / `_parent_record` / `_meta.object_type_id` は `render` の subtree guard・`page_path`・アンカー合成が Python 側で読むだけで、テンプレートからは元々使われていない。
