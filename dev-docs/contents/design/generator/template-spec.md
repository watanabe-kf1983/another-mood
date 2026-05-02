# Template Specification

テンプレートの仕様。views データを Markdown ドキュメントに変換する表現層を定義する。

## 基本方針

- テンプレートのデータソースは常に `compose_dir` のみ
- normalized データは自動的に view になるため、パススルークエリは不要（[queries-spec.md](../composer/queries-spec.md) 参照）

## ファイル構成

`templates_dir`（デフォルト: `docs/definition/templates/`）配下に配置する。拡張子は `.md`（シンタックスハイライト対応）。

```
{templates_dir}/
  index.md                   # エントリポイント（必須）
  erd.md                     # パーシャル
  entity-detail.md           # パーシャル
  mermaid-er.mermaid         # パーシャル（Mermaid エスケープ）
```

## index テンプレート

ユーザが必ず書くエントリポイント。ドキュメント全体の構成（TOC）を定義する:

```jinja2
{# templates/index.md #}
# システム仕様書

{% mood_view prose[id="internal/architecture.md"] %}
{% mood_view "erd" for views.erds %}
{% mood_view prose[id="design/normalizer/schema-spec.md"] %}
{% mood_view "screen" for views.screens %}
```

構造化データの view と prose（Markdown データソース）を自由に混在できる。prose は `contents_dir` に配置した Markdown ファイルから自動生成される view である（[markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照）。

読者や目的が異なる場合は index テンプレートを分ける（社内向け、顧客向け等）。

## `{% mood_view %}` カスタムタグ

`{% mood_view %}` は描画をパーシャルテンプレートに委譲する。`paginate` 設定に応じた分割/インライン判定については [paging-spec.md](paging-spec.md) を参照。

```jinja2
{# templates/erd.md #}
# {{ entry.title }}

{% mood_view "entity-detail" for entry.entities %}
{% mood_view "mermaid-er" with entry.relations %}
```

### inline オプション

> **未着手** — P2 で対応予定。

強制インライン展開用のキーワード。`{% mood_view %}` の振る舞いを、その呼び出し時
に限って「インライン」に固定する:

```jinja2
{% mood_view "name" with data inline %}
```

この形式では、セクションの描画結果がファイルに書き出されず、呼び出し元の
テンプレートにそのまま埋め込まれる (`{% include %}` に近い動作)。

#### 用途

F3 の Query View で Definition / Output Schema / Results を 1 ページに
縦並びで表示する際に使う。`{% mood_view %}` デフォルトの「別ファイル出力」では
3 セクションが別々のページに散ってしまうため、明示的な `inline` 指定で
1 ページに集約する (SQL クライアントの query + result pane パターン)。

Entity の Schema と Data を 1 ページに統合したい用途もあり得るが、現状は
別ページ + 相互リンクで運用している (結合度に基づく非対称設計、
[meta-documentation.md](../app/meta-documentation.md) 参照)。

#### C4 (paginate 自動判定) との関係

C4 では `paginate` 設定を見て `mood_view` が自動的に inline / 分割を判定する
予定。`inline` キーワードはその自動判定を上書きする明示指定として P2 で先行
実装する。C4 導入後も「常に inline を強制する escape hatch」として残すか、
深い統合で吸収するかは C4 実装時に判断。

## Undefined アクセスの扱い

テンプレート内で未定義の変数や属性へアクセスしてもエラーにはならず、空文字列としてレンダリングされる。属性のチェインアクセス（例: `field.metadata.title`）も同様で、途中のキーが存在しなくても空文字列になる。

したがって optional なフィールドを参照する際、`if metadata is defined` や `{{ field.metadata.title if field.metadata else "" }}` のようなガードは不要:

```jinja2
{# metadata や metadata.title が存在しなくても安全 #}
| {{ field.id }} | {{ field.metadata.title }} |
```

### 背景: なぜ Undefined をエラーにしないか

Jinja2 は `undefined` クラスを差し替え可能で、厳密な `StrictUndefined`（全ての undefined アクセスでエラー）、チェイン可能な `ChainableUndefined`、デフォルトの `Undefined`（1 階層目はサイレント、チェインはエラー）の 3 段階を提供する。

本プロジェクトは `ChainableUndefined` を採用する。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- デフォルトの `Undefined` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `StrictUndefined` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）
