# Template Specification

テンプレートの仕様。views データを Markdown ドキュメントに変換する表現層を定義する。

## 基本方針

- テンプレートのデータソースは常に `viewsDir` のみ
- normalized データは自動的に view になるため、パススルークエリは不要（[queries-spec.md](../composer/queries-spec.md) 参照）

## ファイル構成

`templatesDir`（デフォルト: `docs/definition/templates/`）配下に配置する。拡張子は `.md`（シンタックスハイライト対応）。

```
{templatesDir}/
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

{% section prose[id="internal/architecture.md"] %}
{% section "erd" for views.erds %}
{% section prose[id="external/normalizer/schema-spec.md"] %}
{% section "screen" for views.screens %}
```

構造化データの view と prose（Markdown データソース）を自由に混在できる。prose は `contentsDir` に配置した Markdown ファイルから自動生成される view である（[markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照）。

読者や目的が異なる場合は index テンプレートを分ける（社内向け、顧客向け等）。

## `{% section %}` カスタムタグ

`{% section %}` は描画をパーシャルテンプレートに委譲する。`paginate` 設定に応じた分割/インライン判定については [paging-spec.md](paging-spec.md) を参照。

```jinja2
{# templates/erd.md #}
# {{ entry.title }}

{% section "entity-detail" for entry.entities %}
{% section "mermaid-er" with entry.relations %}
```

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
