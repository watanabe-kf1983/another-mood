# Markdown Parser Specification

## Internal Design

### 実装方針

- Markdown AST: markdown-it-py（CommonMark 準拠、AST 走査で見出し抽出・リンク検出）
- YAML 出力: ruamel.yaml（YAML 1.2、literal block scalar で Markdown 本文を可読に保持）

### リンク正規化

prose 本文中の相対リンクを `node:` アンカーパス記法（インラインリンク形）に変換する。preprocess の prose パスが、生成側フィルタ `relink`（`node:` → URL、[generator.md](../generator/generator.md#リンク解決)）の **逆向き処理** として本文 (`body.content`) のリンクを書き換える。解決はレキシカル（FS チェックなし）で、リンク先 prose の存在検証は relink（Generate フェーズ）に委ねる。実装は preprocess の `normalize_links`（`prose.py`）と shared/markdown の `rewrite_inline_links`。

変換対象は **contents 内に解決する相対 `.md` リンクのみ**:

- `[t](rel.md)` / `[t](rel.md#frag)` → `node:/prose/<解決後 id>`（`#frag` は落とす）
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

ページ部 (`/prose/...`) は prose の `/`-素通し例外（[anchor-spec.md](../generator/anchor-spec.md#prose-の例外)）でファイル相対パスがそのまま埋まる。

#### 背景: cross-doc リンクを全て node: 化し fragment を落とす理由

path+fragment リンクを「fragment 落とし」で変換するのは、次の優先タスク **C5/C6（edition 別出力・複数 edition 並列ビルド）** で「きりだし単位が変わったときのリンク先の動的解決」を検証したいため。生の相対リンクは静的で、別構造の出力では壊れる。cross-doc リンクを全て `node:` 化して relink の動的解決下に置けば、出力構造が変わってもリンクが追従する。落とした fragment の精度は A7（[見出し fragment 対応](#見出し-fragment-対応-a7)）で回復する。

#### 背景: 純 #frag を恒久的に非変換とする理由

prose ファイルは **必ず全体が 1 ページに描画される** 不変条件を持つ（分割対象は query 由来のコレクションであって prose ドキュメント自身ではない）。同一ドキュメント内の `#frag` は Goldmark の native id で常に同一ページ内に着地するので壊れず、`node:` 化は不要。機械チェック（[B10](node:/tasks/B/tasks/B10)）目的の変換は過保護なので採らない。

#### 背景: ソースの可搬性

ソース Markdown では普通の相対パスでリンクを記述する。これにより:

- GitHub 上でリンクがそのまま動作する（見出し fragment も github-slug 同士で着地する）
- エディタのリンクジャンプが機能する
- 独自記法によるソース汚染がない

`node:` 記法への変換は Normalizer が自動的に行うため、ユーザがリンク記法を意識する必要はない。

## Proposals

### 見出し抽出 (A1)

> **未実装** — Phase 12 タスク [A1](node:/tasks/A/tasks/A1)。anchor 側の住所付け・リンク解決への波及は [anchor-spec.md の見出しノード](../generator/anchor-spec.md#見出しノード-a3-a4)（A3, A4）。

prose 本文中の見出しを **リンクの着地点** として抽出する。セクション単位レコードは作らない（本文はファイル単位レコードに一度きり）。

#### 背景: セクション単位抽出をやめた理由

当初案は `{#id}` 付き見出しごとにセクション単位レコードを生成していた（ファイル単位レコードと本文が重複＝ダブルカウント）。これを廃する:

- **ダブルカウント** — セクションレコードがファイル本文の一部のコピーを持ち、同じ散文が二重に乗る
- **複雑さの割に効用が薄い** — 本文範囲切り出し・ダブル出力・見出しレベル正規化は、レコードを増やすためだけのコスト。実需は「他文書の特定見出しにリンクを張れること」だけ

そこで見出しは **node（リンクの宛先）** とし、レコードにはしない。本文は一度きり、見出しはその中の住所だけを持つ。

#### 見出しの id は見出しテキストの github-slug

`{#id}` 記法は使わない。見出しの id は **見出しテキストから導出する github 互換 slug**:

- lowercase・空白→`-`・記号除去・CJK はそのまま残す・同一ファイル内の重複は `-N` 連番
- `## エラー処理` → `エラー処理`、`## API の設計` → `api-の設計`

`{#id}` で id を固定すると **見出しテキストと乖離していく**。テキスト由来にすれば id とタイトルが原理的にズレない。安定性は「id が不変であること」ではなく **「壊れた参照は必ずビルドで報告される」** で担保する（[anchor-spec.md の未解決参照の扱い](../generator/anchor-spec.md#未解決参照の扱い)）。

> **背景: なぜ github 互換 slug か.** CommonMark/GitHub 圏のデファクト標準であり、かつ本ツールのレンダラ Hugo/Goldmark が既定 (`autoHeadingIDType = "github"`) で見出し id をこの方式で打つ。slug を github 互換にすれば **出力 HTML（Goldmark）にも GitHub 上の素 Markdown にも同じ id で着地** する。本文はほぼ CJK 見出しで、github 方式も IRI も CJK をそのまま残すため差は小さい。

#### 見出しは prose 配下の nested リストに持つ

見出しは prose レコード配下の `headings` リストとして materialize する。これがリンク解決用の node の正本で、各見出しはネストしたリスト要素＝ node となり anchor_path が `/prose/X#slug` に組まれる（[anchor-spec.md の見出しノード](../generator/anchor-spec.md#見出しノード-a3-a4)）。本文 (`body`) は重複させない:

```yaml
prose:
  - id: design/normalizer/architecture
    title: アーキテクチャ
    body: {mime_type: text/markdown, content: "..."}   # 本文は一度きり
    headings:
      - {id: エラー処理, title: エラー処理, level: 2}
      - {id: api-の設計, title: API の設計, level: 3}   # id=slug, title=テキスト
```

重複するのは `{slug, title, level}` の **メタデータ（住所）だけ** で、本文テキストは複製されない（廃したセクションレコードはここを重複させていた）。

#### 見出しリンクの妥当性は Generate で検証する

見出しへの参照は **ドキュメント間のクロスリンク** であり、妥当性は **Generate フェーズのリンク解決** で見る — `node:/prose/X#slug` が node index で解決できなければ MissingNode として可視化される（[未解決参照の扱い](../generator/anchor-spec.md#未解決参照の扱い)、ビルドレポート化は [B10](node:/tasks/B/tasks/B10)）。データ層の FK（x-ref）は使わず、見出しを FK ターゲットにする派生 entity も作らない。

> **背景: 見出しに FK をかけない理由.** FK（x-ref）の本分は **生 entity 間の整合＝クエリでの結合先の保証** で、検証は preprocess（[schema-spec.md](schema-spec.md#参照整合性制約-x-ref)）。文書間のリンクは出力世界の関心で、妥当性は Generate が見る — 二層を混ぜない。見出しの実需は **リンクであって結合ではない** ので FK は持ち込まない。なお見出しは本質的に複合キー `(prose, slug)` を持つため、仮に FK で縛るなら複合 FK 機構が要る（x-ref は単一列、複合キー対応は [D8/D9](node:/tasks/D/tasks/D8) で未決）。`<prose-id>#<slug>` を1列に連結して単一 FK で縛るのは複合キーのエミュレーションで歪むため採らない。生 entity 間で見出しへの結合整合が本当に要るときに、複合 FK を別途検討する。

#### スコープ

当面 **prose 限定**。任意の `text/markdown` body からの見出し抽出への一般化は、散文サブシステムの媒体非依存化（[H3](node:/tasks/H/tasks/H3)）と地続きなので、そこで扱う。

### 見出し fragment 対応 (A7)

> **未実装** — Phase 12 タスク [A7](node:/tasks/A/tasks/A7)。基本変換（A5）は実装済み（[Internal Design のリンク正規化](#リンク正規化)）。本タスクは見出しノード（[見出し抽出](#見出し抽出-a1)・[anchor-spec.md A3, A4](../generator/anchor-spec.md#見出しノード-a3-a4)）を前提とする後続で、A5 が `node:` 化の際に落とした `#fragment` を、見出しノードが住所を持ってから透過で運ぶ。

`[text](relative/path.md#見出し-slug)` の `#見出し-slug` を、解決後の `node:` URI の fragment としてそのまま運ぶ:

```markdown
[エラー処理](architecture.md#エラー処理)
↓
[エラー処理](node:/prose/design/normalizer/architecture#エラー処理)
```

`#見出し-slug` がページ内の見出しを指す。fragment は **著者が書いた slug をそのまま素通し**（生成側で再 slug しない）。見出しが対象 prose に存在しなければ relink が解決失敗として可視化する（[未解決参照の扱い](../generator/anchor-spec.md#未解決参照の扱い)）。
