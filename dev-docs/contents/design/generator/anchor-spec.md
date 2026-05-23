# Anchor Specification

アンカー（リンク可能なオブジェクト）の識別とリンク解決の仕様。アンカーを一意に指す文字列を **アンカー ID** と呼ぶ。

## Proposals

> **未実装** — Phase 11 タスク [B1〜B6](../../../tasks.md)（ラッパーツリー / アンカー ID 生成規則 / オンデマンド走査 / `link_md` フィルタ / `toc:id` 解決 / `get_page_url`）

### 用語

- **アンカー (anchor)**: リンクされ得る位置・対象。HTML/Markdown の anchor target と同義。本ツールではデータツリー上の各ノードがアンカーとなる
- **アンカー ID (anchor ID)**: そのアンカーを一意に識別する文字列。本ツールが生成する。URL fragment として URL に埋め込まれる

### ID 体系

アンカー ID は **データツリー上のパス** を `/` 区切りで表現した文字列。

#### セグメント構成

データツリーを root から目的のノードまで辿り、各ステップを 1 セグメントとして書き出す:

- **dict キー（singleton 配下のキー）**: そのキーをそのまま使う
- **リスト要素**: その要素の `id` フィールドの値を使う

リスト要素に `id` フィールドが無い場合（Array pattern で id を schema 上要求していない場合、[schema-spec.md](../normalizer/schema-spec.md) 参照）、その要素はアンカー ID を持たない。到達経路を表現する手段がないため、配下のオブジェクトもアンカー ID を持たない。

#### Escape 規則

アンカー ID は URL fragment として埋め込まれる文字列。`/` を path 区切り文字として予約しているため、**id 値が `/` を含む場合は percent-encoding (`%2F`) で escape する**。

その他の URL-fragment-unsafe な文字（空白、`#` 等）も percent-encoding する。HTML5 の `id` 属性が空白を許容しないため、空白を含む id を持つレコードは技術的にアンカー ID 化不可（[未決事項](#未決事項)参照）。

#### Prose の例外

`prose` entity に限り、id 内の `/` を escape **せず** にアンカー ID へ素通しで埋め込む。

理由:

- `prose` の id は contents/ 内ファイルの相対パスから生成され、構造的にパス階層を持つ。これを `%2F` でエンコードすると `prose/design%2Farchitecture` のような可読性の低い文字列になる
- `prose` は flat な配列 entity で sub-entity を持たないため、resolver が `prose/` 以降を「単一の id」として扱えば曖昧性は発生しない

この例外は `prose` に固有のものとして明示的に定義する。一般化（「sub-entity を持たない配列 entity 一般に適用」等）はしない — 利用者 entity の構造変化に伴う将来の曖昧性混入を避けるため。

#### 例

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

screens:
  - id: user-list
    title: ユーザー一覧画面

prose:                             # flat list、id はファイル相対パス
  - id: design/architecture
    title: Architecture
  - id: design/normalizer/schema-spec
    title: Schema Specification
```

| アンカー ID | 指す対象 |
|---|---|
| `overview` | overview singleton |
| `erds/user-management` | user-management の ER図 |
| `erds/user-management/entities/user` | user-management 配下の user エンティティ |
| `erds/order-flow/entities/user` | order-flow 配下の user エンティティ（衝突しない） |
| `screens/user-list` | user-list 画面 |
| `prose/design/architecture` | Architecture 散文（id 内 `/` を素通し） |
| `prose/design/normalizer/schema-spec` | Schema Specification 散文 |

旧仕様（`{class}.item.{id}` 形式）と異なり、新仕様ではアンカー ID が **データツリー上の到達経路そのもの** で構成されるため、ネストしたリスト要素間で id が重複してもアンカー ID が衝突しない。

#### クラスとの関係

class（[schema-spec.md](../normalizer/schema-spec.md) の Entity ID および ObjectType ID）は **型レベルの識別子** で、アンカー ID とは直交する概念:

- **class**: schema 上の位置を示す path-based 名（例: `categories.tasks`, `categories.item.tasks.item`）。クエリ DSL の `from:`、paging 設定、FK 解決、表示見出しで参照される
- **アンカー ID**: データツリー上の実体パス（例: `categories/web/tasks/foo`）。リンク解決でのみ使われる

旧仕様ではアンカー ID を `{class}.{id}` と class 名込みで構築していたが、新仕様ではアンカー ID は実体パスのみで構成する。class はアンカー ID 構築には登場しない。

### リンク記法

テンプレート内では `link_md` フィルタを使う:

```jinja2
{{ "erds/user-management/entities/user" | link_md }}
```

Markdown data 内では `toc:` 記法を使う（プレフィックス名は実装時に再検討、現状は暫定）:

```markdown
ユーザーの詳細は[ユーザー](toc:erds/user-management/entities/user)を参照。
```

Markdown データソースでは、Normalizer がソース内の相対リンクを自動的に `toc:` 記法に変換する（[markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照）:

```markdown
{# ソース: {contents_dir}/design/normalizer/normalizer.md #}
[Composer](../composer/composer.md)
↓ Normalizer が変換 ↓
[Composer](toc:prose/design/composer/composer)
```

### リンク解決

アンカー ID から実際のリンク先 URL への解決は paging 設定に依存する（[paging-spec.md](paging-spec.md) 参照）。エンジンがアンカー ID を適切な相対パス + fragment に置換する。

例: `[ユーザー](../erds/user-management.md#erds/user-management/entities/user)`

prose 例外の resolver 側挙動: アンカー ID を path 区切り文字 `/` で分割しつつ走査するが、`prose/` を先頭セグメントに見たときは残り全体を単一の id とみなして flat list を引く。例外はアンカー ID 構築側（escape 省略）と整合する形で resolver にも 1 箇所だけ規則を入れる。

### 未決事項

- **空白を含む id の扱い**: HTML5 の `id` 属性は空白不可のため、空白を含む id はアンカー ID 化不可。ビルド時に警告して当該 id 配下をアンカー ID 無し扱いとする方針（[F4 / D 群と連携、未タスク化](../../../tasks.md)）
- **`toc:` プレフィックスの名前**: 実態は「アンカー参照」で TOC ではない。実装時（[B4, B5](../../../tasks.md)）に再検討する
