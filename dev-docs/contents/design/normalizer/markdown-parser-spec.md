# Markdown Parser Specification

## Internal Design

### 実装方針

- Markdown AST: markdown-it-py（CommonMark 準拠、AST 走査で見出し抽出・リンク検出）
- YAML 出力: ruamel.yaml（YAML 1.2、literal block scalar で Markdown 本文を可読に保持）

## Proposals

### 見出し抽出 (A1, A2)

> **未実装** — Phase 12 タスク [A1, A2](node:/tasks/A/tasks/A1)。anchor 側の住所付け・リンク解決への波及は [anchor-spec.md の見出しノード](../generator/anchor-spec.md#見出しノード-a3-a4)（A3, A4）。

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

#### 二つの materialize: nested canonical と prose_headings 索引

見出しは二つの世界で使われる — リンク解決（出力世界）と FK・横断クエリ（データ／関係世界）。各世界が既存機構だけで扱えるよう、**両方の形で materialize する**（どちらも同じ parse から決定的に派生するため乖離しえない）:

1. **nested（canonical）** — prose レコード配下の `headings` リスト。リンク世界の正本。各見出しはネストしたリスト要素＝ node で、anchor_path が `/prose/X#slug` に組まれる（[anchor-spec.md の見出しノード](../generator/anchor-spec.md#見出しノード-a3-a4)）

   ```yaml
   prose:
     - id: design/normalizer/architecture
       title: アーキテクチャ
       body: {mime_type: text/markdown, content: "..."}   # 本文は一度きり
       headings:
         - {id: エラー処理, title: エラー処理, level: 2}
         - {id: api-の設計, title: API の設計, level: 3}   # id=slug, title=テキスト
   ```

2. **prose_headings（派生索引）** — トップレベルの派生 entity。関係世界（FK・横断クエリ）用。id は **グローバルに一意な複合キー `<prose-id>#<slug>`**、`prose` フィールドが prose を x-ref する

   ```yaml
   prose_headings:
     - id: design/normalizer/architecture#エラー処理
       prose: design/normalizer/architecture     # x-ref → prose.id
       title: エラー処理
       level: 2
   ```

> **背景: なぜ二つ持つか（ダブルカウントとの違い）.** 廃したセクションレコードは **本文テキストのコピー** を重複させていた。ここで重複するのは `{slug, title, level}` の **メタデータ（索引）だけ** で、本文は nested 側にも乗らない（prose レコードの `body` に一度きり）。prose_headings は「canonical な見出しの、関係アクセス用に materialize した索引」であり、索引は定義上アクセスのための派生重複なので smell ではない。

#### 見出しへの参照整合性 (FK)

見出しへの FK は **prose_headings（トップレベル entity）を既存の FK 機構でターゲットにする**。FK 機構の拡張も例外も要らない:

```yaml
# 例: タスクの spec フィールドが特定見出しを指す
spec:
  type: string
  x-ref: {entity: prose_headings, attribute: id}   # 値 "design/.../architecture#エラー処理"
```

これは schema-spec.md「[なぜ参照先を top-level entity のみに限定したか](schema-spec.md#背景-なぜ参照先を-top-level-entity-のみに限定したか)」の原則 — *「ネスト先が他から参照されるニーズが surface したら、ネストパスを target にする構文拡張ではなく、別 entity に切り出す」* — の素直な適用。見出しはまさにその「他から参照される弱エンティティ」で、prose_headings として切り出す。`prose_headings.prose → prose.id` の x-ref も既存機構で、各見出しが実在 doc に属する整合性を与える。

> **背景: FK とリンク解決を混ぜない.** FK は JOIN 可能性を保証する RDB 世界の道具（preprocess）、リンク解決は node index を引く出力世界（generator）。見出しは両世界に姿を持つ（prose_headings = データ、見出しノード = リンク先）が、これは全エンティティが持つ二面性と同じで特別な統合ではない。FK は prose_headings を、リンクは node index を引く。依存方向（preprocess → generator）も保たれる。

#### スコープ

当面 **prose 限定**。任意の `text/markdown` body からの見出し抽出への一般化は、散文サブシステムの媒体非依存化（[H3](node:/tasks/H/tasks/H3)）と地続きなので、そこで扱う。

### リンク正規化 (A5, A7)

> **未実装** — Phase 12。**A5（基本変換: 相対パス → `node:`）** は見出し抽出に依存せず単独で実装できる。**A7（見出し fragment 対応）** は見出しノード（[見出し抽出](#見出し抽出-a1-a2)）を前提とする後続。タスク [A5](node:/tasks/A/tasks/A5) / [A7](node:/tasks/A/tasks/A7)。

ソース Markdown 内の相対リンクを `node:` アンカーパス記法（インラインリンク形）に変換する。

#### 基本変換 (A5)

1. Markdown リンク `[text](relative/path.md)` を検出
2. 相対パスを `contents_dir` 基点の正規化パスに解決
3. 対応する prose レコードのアンカーパス記法 (`node:/...`) に変換

#### 例

`{contents_dir}/design/normalizer/normalizer.md` 内:

```markdown
処理フローの詳細は[Composer](../composer/composer.md)を参照。
```

↓ 正規化 ↓

```markdown
処理フローの詳細は[Composer](node:/prose/design/composer/composer)を参照。
```

ページ部 (`/prose/...`) は prose の `/`-素通し例外（[anchor-spec.md](../generator/anchor-spec.md#prose-の例外)）でファイル相対パスがそのまま埋まる。`node:` リンクの解決は Document Generator の pre-render フィルタ `relink` が行う（[generator.md](../generator/generator.md#リンク解決) 参照）。

#### 見出し fragment 対応 (A7)

> **前提** — 見出し抽出（A1, A2）と見出しノードの住所付け（[anchor-spec.md A3, A4](../generator/anchor-spec.md#見出しノード-a3-a4)）。A5 の後・見出しノードが解決可能になってから着手する。

`[text](relative/path.md#見出し-slug)` の `#見出し-slug` を、解決後の `node:` URI の fragment としてそのまま運ぶ:

```markdown
[エラー処理](architecture.md#エラー処理)
↓
[エラー処理](node:/prose/design/normalizer/architecture#エラー処理)
```

`#見出し-slug` がページ内の見出しを指す。fragment は **著者が書いた slug をそのまま素通し**（生成側で再 slug しない）。見出しが対象 prose に存在しなければ relink が解決失敗として可視化する（[未解決参照の扱い](../generator/anchor-spec.md#未解決参照の扱い)）。

#### 背景: ソースの可搬性

ソース Markdown では普通の相対パスでリンクを記述する。これにより:

- GitHub 上でリンクがそのまま動作する（見出し fragment も github-slug 同士で着地する）
- エディタのリンクジャンプが機能する
- 独自記法によるソース汚染がない

`node:` 記法への変換は Normalizer が自動的に行うため、ユーザがリンク記法を意識する必要はない。
