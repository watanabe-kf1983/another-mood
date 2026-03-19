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
