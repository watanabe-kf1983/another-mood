# Anchor Specification

アンカー（リンク可能なオブジェクト）の識別とリンク解決の仕様。アンカーを一意に指す文字列を **アンカーパス** と呼ぶ。

## Proposals

> **未実装** — Phase 11 タスク [B4, B5, B6](../../../tasks.md)（anchor フィルタ群 / prose body `resolve` フィルタ / `_meta.page_path` 算出）。親参照注入 (B1)・`_meta.anchor_path` / `_meta.object_type_id` 注入 (B3)・anchor_path → ノードマップ (B2) は実装済み — [generator.md](generator.md#%E3%83%8E%E3%83%BC%E3%83%89%E3%83%A1%E3%82%BF%E3%83%87%E3%83%BC%E3%82%BF) 参照。

### 用語

- **アンカー (anchor)**: リンクされ得る位置・対象。HTML/Markdown の anchor target と同義。本ツールではデータツリー上の各ノードがアンカーとなる
- **アンカーパス (anchor path)**: そのアンカーを一意に識別する文字列。本ツールが生成する。URL fragment として URL に埋め込まれる

### ID 体系

アンカーパスは **データツリー上のパス** を `/` 区切りで表現した文字列。root を `/` とする **絶対パス形式**で、先頭の `/` が「データツリー root を起点とする絶対座標」であることを示す（相対参照と区別される）。

#### セグメント構成

データツリーを root から目的のノードまで辿り、各ステップを 1 セグメントとして書き出す:

- **dict キー（singleton 配下のキー）**: そのキーをそのまま使う
- **リスト要素**: その要素の `id` フィールドの値を使う

リスト要素に `id` フィールドが無い場合（Array pattern で id を schema 上要求していない場合、[schema-spec.md](../normalizer/schema-spec.md) 参照）、その要素はアンカーパスを持たない。到達経路を表現する手段がないため、配下のオブジェクトもアンカーパスを持たない。

#### Escape 規則

アンカーパスは URL fragment として埋め込まれる文字列。`/` を path 区切り文字として予約しているため、**id 値が `/` を含む場合は percent-encoding (`%2F`) で escape する**。

その他の URL-fragment-unsafe な文字（空白、`#` 等）も percent-encoding する。HTML5 の `id` 属性が空白を許容しないため、空白を含む id を持つレコードは技術的にアンカーパス化不可（[未決事項](#未決事項)参照）。

#### Prose の例外

`prose` entity に限り、id 内の `/` を escape **せず** にアンカーパスへ素通しで埋め込む。

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

| アンカーパス | 指す対象 |
|---|---|
| `/` | root（views 全体） |
| `/overview` | overview singleton |
| `/erds/user-management` | user-management の ER図 |
| `/erds/user-management/entities/user` | user-management 配下の user エンティティ |
| `/erds/order-flow/entities/user` | order-flow 配下の user エンティティ（衝突しない） |
| `/screens/user-list` | user-list 画面 |
| `/prose/design/architecture` | Architecture 散文（id 内 `/` を素通し） |
| `/prose/design/normalizer/schema-spec` | Schema Specification 散文 |

旧仕様（`{class}.item.{id}` 形式）と異なり、新仕様ではアンカーパスが **データツリー上の到達経路そのもの** で構成されるため、ネストしたリスト要素間で id が重複してもアンカーパスが衝突しない。

#### クラスとの関係

class（[schema-spec.md](../normalizer/schema-spec.md) の Entity ID および ObjectType ID）は **型レベルの識別子** で、アンカーパスとは直交する概念:

- **class**: schema 上の位置を示す path-based 名（例: `categories.tasks`, `categories.item.tasks.item`）。クエリ DSL の `from:`、paging 設定、FK 解決、表示見出しで参照される
- **アンカーパス**: データツリー上の実体パス（例: `/categories/web/tasks/foo`）。リンク解決でのみ使われる

旧仕様ではアンカーパスを `{class}.{id}` と class 名込みで構築していたが、新仕様ではアンカーパスは実体パスのみで構成する。class はアンカーパス構築には登場しない。

### リンク記法

#### テンプレート内のアンカー参照

テンプレート内では anchor path から 3 種類のフィルタを使い分ける:

```jinja2
{{ "/erds/user-management/entities/user" | anchor_link }}
{# → [<display>](<URL>) 形式の Markdown リンク #}

{{ "/erds/user-management/entities/user" | anchor_link("ER 図") }}
{# → display text を明示。[ER 図](<URL>) #}

{{ "/erds/user-management/entities/user" | anchor_title }}
{# → display 文字列のみ #}

{{ "/erds/user-management/entities/user" | anchor_url }}
{# → URL 文字列のみ #}
```

display text は対象ノードから `title` → `name` → `id` → anchor_path 全体 のチェインで解決する。「末尾セグメント」を fallback に入れないのは、それが意味を持つのはリスト要素か入れ子オブジェクトに限られ、一般化できる fallback ではないため。`anchor_link(arg)` のように引数で渡せば override。

#### Markdown 本文中のアンカー参照

prose body 等の Markdown 本文では `toc:` プレフィックス記法でアンカーパスを URL として埋め込む:

```markdown
ユーザーの詳細は[ユーザー](toc:/erds/user-management/entities/user)を参照。
```

この記法は二役を兼ねる:

1. **author 向け sugar** — author が anchor で明示的に参照したいときの書き方
2. **canonical intermediate form** — Normalizer がソース相対リンクから変換した先の中間表現

ソース Markdown では普通の相対パスで書け、Normalizer が `toc:` 記法に変換する ([markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照):

```markdown
{# ソース: {contents_dir}/design/normalizer/normalizer.md #}
[Composer](../composer/composer.md)
↓ Normalizer が変換 ↓
[Composer](toc:/prose/design/composer/composer)
```

### リンク解決

リンク解決は Generator の **pre-render 段階で完結**する。post-render での文字列置換は行わない。

- **`anchor_link` / `anchor_title` / `anchor_url` フィルタ**: テンプレート内で anchor path から Markdown リンク / display text / URL を生成
- **prose body 処理フィルタ (仮称 `resolve`)**: prose body 中の `toc:` URL を実 URL に置換。anchor 解決以外にも見出しレベル正規化やエスケープ調整等を兼ねる総合処理フィルタ

出力する URL は **対象ページへの相対パス** + URL fragment。例: `[ユーザー](../erds/user-management.md#/erds/user-management/entities/user)`。

URL は **path 部 + fragment 部** に分けて組み立てる:

- **path 部**: source ページから target ページへの相対パス
- **fragment 部**: target ノードの `_meta.anchor_path` をそのまま使う (full anchor_path 形式)。HTML id 側も同じ文字列で発行する ([generator.md](generator.md) の id 発行と対応)。常に付与する (target がページ root に一致する場合も省かない — ハンドリングを単純に保つ)

resolver とフィルタは **out_dir-relative 座標系**で動く:

- **source ページパス**: render に渡された node の `_meta.page_path` ([B6](../../../tasks.md))。`@pass_context` フィルタが `ctx["_meta"]["page_path"]` として読む
- **target ページパス**: anchor_path → ノードマップで target ノードを引いて `_meta.page_path` を取得
- **path 部の算出**: フィルタが `os.path.relpath(target_page_path, source_page_path.parent)` で計算
- **最終 URL**: `{path 部}#{target._meta.anchor_path}`

`_meta` に持たせるのは **path のみ** (`_meta.page_url` のような結合済み URL 文字列はノードに持たない)。fragment は常に anchor_path から派生するので、結合は URL を必要とするフィルタ側でその場で行う。

フィルタは `@pass_context` で受ける必要がある。理由は二つ: (1) ctx 経由で source 側 page path を読む、(2) Jinja2 オプティマイザの定数畳み込みを抑止する — 定数引数の `{{ "/erds/x" | anchor_link }}` を許すとコンパイル時に評価されて URL がキャッシュに焼かれ、同テンプレートを別ページから使ったときに相対 URL が壊れる。

いずれのフィルタも内部で同じ resolver を共有 (closure binding 経由)、anchor_path → ノードのマップを引いて URL を組み立てる。

prose 例外の resolver 側挙動: マップは full anchor_path をキーにするフラットな dict ([generator.md](generator.md#anchor_path--%E3%83%8E%E3%83%BC%E3%83%89%E3%83%9E%E3%83%83%E3%83%97) の B2) なので、resolver はアンカーパスを分割せず**そのままキーで引く**。prose の `/` 素通しはアンカーパス構築側で吸収済みのため、resolver 側に prose 例外の特別扱いは要らない（例: `/prose/design/architecture` はそのキーで直に当たる）。

### 未決事項

- **空白を含む id の扱い**: HTML5 の `id` 属性は空白不可のため、空白を含む id はアンカーパス化不可。ビルド時に警告して当該 id 配下をアンカーパス無し扱いとする方針（[F4 / D 群と連携、未タスク化](../../../tasks.md)）
- **`toc:` プレフィックスの名前**: 実態は「アンカー参照」で TOC ではない。実装時（[B4, B5](../../../tasks.md)）に再検討する
