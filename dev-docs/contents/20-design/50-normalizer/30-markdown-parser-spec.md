# Markdown Parser Specification

散文の順序・構造は [Prose](../45-prose-spec.md)。本章は Markdown のパース — 相対リンクの `node:` 正規化と見出し抽出 — を扱う。

## Internal Design

### 実装方針

- Markdown AST: markdown-it-py（CommonMark 準拠、AST 走査で見出し抽出・リンク検出）
- YAML 出力: ruamel.yaml（YAML 1.2、literal block scalar で Markdown 本文を可読に保持）

### リンク正規化

prose 本文中の相対リンクを `node:` アンカーパス記法（インラインリンク形）に変換する。preprocess の prose パスが、生成側フィルタ `relink`（`node:` → URL、[generator.md](../70-generator/10-generator.md#リンク解決)）の **逆向き処理** として本文 (`body.content`) のリンクを書き換える。解決はレキシカル（FS チェックなし）で、リンク先 prose の存在検証は relink（Generate フェーズ）に委ねる。実装は preprocess の `normalize_links`（`prose.py`）と shared/markdown の `rewrite_inline_links`。

変換対象は **contents 内に解決する相対 `.md` リンクのみ**:

- `[t](rel.md)` → `node:/prose/<解決後 id>`
- `[t](rel.md#見出し-slug)` → `node:/prose/<解決後 id>#見出し-slug`（`#fragment` は著者が書いた slug を **素通し** — 再 slug・encode しない。ページ内見出しを指し、対象 prose に無ければ relink が解決失敗として可視化する（[anchor-spec.md の未解決参照の扱い](../70-generator/20-anchor-spec.md#未解決参照の扱い)））
- 次は **verbatim**（非変換）: 純 `#frag`（同一ページ参照）／ contents 外への脱出（`../` 突き抜け）／スキーム付き（`http:` `node:` `mailto:` 等）／絶対パス（先頭 `/`）／`.md` 以外（画像・スタイル等）／コード（fence・inline）内のリンク

#### 例

`{contents_dir}/design/normalizer/normalizer.md` 内:

```markdown
処理フローの詳細は[Composer](../composer/composer.md)を参照。
```

↓ 正規化 ↓

```markdown
処理フローの詳細は[Composer](node:/prose/design/composer/composer)を参照。
```

ページ部 (`/prose/...`) は prose の `/`-素通し例外（[anchor-spec.md](../70-generator/20-anchor-spec.md#prose-の例外)）でファイル相対パスがそのまま埋まる。

#### 背景: cross-doc リンクを全て node: 化する理由

**C5/C6（edition 別出力・複数 edition 並列ビルド）** で「きりだし単位が変わったときのリンク先の動的解決」を検証したいため。生の相対リンクは静的で、別構造の出力では壊れる。cross-doc リンクを全て `node:` 化して relink の動的解決下に置けば、出力構造が変わってもリンクが追従する。`#fragment` も同じ理由で `node:` URI に乗せて運ぶ — 出力 URL の path 部が動的に決まっても、fragment はページ内見出しの native id にそのまま着地する。

#### 背景: 純 #frag を恒久的に非変換とする理由

prose ファイルは **必ず全体が 1 ページに描画される** 不変条件を持つ（分割対象は query 由来のコレクションであって prose ドキュメント自身ではない）。同一ドキュメント内の `#frag` は Goldmark の native id で常に同一ページ内に着地するので壊れず、`node:` 化は不要。機械チェック（[B10](node:/tasks/B/tasks/B10)）目的の変換は過保護なので採らない。

#### 背景: ソースの可搬性

ソース Markdown では普通の相対パスでリンクを記述する。これにより:

- GitHub 上でリンクがそのまま動作する（見出し fragment も github-slug 同士で着地する）
- エディタのリンクジャンプが機能する
- 独自記法によるソース汚染がない

`node:` 記法への変換は Normalizer が自動的に行うため、ユーザがリンク記法を意識する必要はない。

### 見出し抽出

prose 本文中の見出しを **リンクの着地点（node）** として抽出し、prose レコード配下の `headings` リストに materialize する。実装は shared/markdown の `heading_nodes` / `github_slug` と、それを prose レコードへ束ねる preprocess の `preprocess_prose`（`prose.py`）。

各見出しは `{id, title, level}` のフラットなリスト要素。ネストしたリスト要素＝ node として anchor_path が `/prose/X#slug` に組まれる（[anchor-spec.md の Prose の例外](../70-generator/20-anchor-spec.md#prose-の例外)）。**セクション単位のレコードは作らず**、本文 (`body`) も重複させない — 重複するのは住所メタデータ `{slug, title, level}` だけ。H1〜H6 の全レベルを採る（レンダラは全見出しに native id を打つので、どのレベルもリンクの着地点になりうる。H1＝タイトルへの `#slug` リンクも解決できる）:

```yaml
prose:
  - id: design/normalizer/architecture
    title: アーキテクチャ                            # first_h1 由来（従来どおり）
    body: {mime_type: text/markdown, content: "..."}   # 本文は一度きり
    headings:
      - {id: アーキテクチャ, title: アーキテクチャ, level: 1}   # H1（タイトル）も着地点
      - {id: エラー処理, title: エラー処理, level: 2}
      - {id: api-の設計, title: API の設計, level: 3}          # id=slug, title=テキスト
```

#### id は見出しテキストの github-slug

`{#id}` 記法は使わない。見出しの id は **見出しテキストから導出する github 互換 slug**（`## API の設計` → `api-の設計`）。`{#id}` で固定すると id と見出しテキストが乖離するが、テキスト由来なら原理的にズレない。安定性は「id が不変であること」ではなく **「壊れた参照は必ずビルドで報告される」** で担保する（[未解決参照の扱い](../70-generator/20-anchor-spec.md#未解決参照の扱い)）。

**合わせる対象は GitHub の見出しアンカー規則であって、レンダラ（Hugo）ではない** — 見出しリンクが我々の Hugo 出力・GitHub・VS Code preview のいずれでも同じ id に着地するため。正本（GitHub 公式 Docs）・実装参照（html-pipeline）・`\p{Word}` を自前判定する理由は `github_slug` の docstring に集約。現実の見出し（ASCII＋CJK 文字）では三者が一致し、テストが Hugo 出力とクロスチェックする。割れるのは exotic 文字だけで、そこは GitHub 準拠を採り、Hugo とのズレは Hugo 側の非互換（レンダラは差し替え可能な依存）として扱う。

#### 見出しリンクの妥当性は Generate で検証する

見出しへの参照は **ドキュメント間のクロスリンク** であり、妥当性は **Generate フェーズのリンク解決** で見る — `node:/prose/X#slug` が node index で解決できなければ MissingNode として可視化される（[未解決参照の扱い](../70-generator/20-anchor-spec.md#未解決参照の扱い)、ビルドレポート化は [B10](node:/tasks/B/tasks/B10)）。データ層の FK（x-ref）は使わず、見出しを FK ターゲットにする派生 entity も作らない。

> **背景: 見出しに FK をかけない理由.** FK（x-ref）の本分は **生 entity 間の整合＝クエリでの結合先の保証** で、検証は preprocess（[schema-spec.md](20-schema-spec.md#参照整合性制約-x-ref)）。文書間のリンクは出力世界の関心で、妥当性は Generate が見る — 二層を混ぜない。見出しの実需は **リンクであって結合ではない** ので FK は持ち込まない。なお見出しは本質的に複合キー `(prose, slug)` を持つため、仮に FK で縛るなら複合 FK 機構が要る（x-ref は単一列、複合キー対応は [D8/D9](node:/tasks/D/tasks/D8) で未決）。`<prose-id>#<slug>` を1列に連結して単一 FK で縛るのは複合キーのエミュレーションで歪むため採らない。生 entity 間で見出しへの結合整合が本当に要るときに、複合 FK を別途検討する。

#### スコープ

当面 **prose 限定**。任意の `text/markdown` body からの見出し抽出への一般化は、散文サブシステムの媒体非依存化と地続きだったが、その担い手だった旧 H3 は「prose と blob を別コレクションにする」判断で棄却された（[normalizer.md「バイナリファイルの取り扱い」](10-normalizer.md#バイナリファイルの取り扱い-h1-h4-h7)）。後継アイデア（text/html blob のページ解釈）が実タスク化するとき、そこで再検討する。
