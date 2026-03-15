# Template Specification

テンプレートの仕様。views データを Markdown ドキュメントに変換する表現層を定義する。

## 基本方針

- テンプレートのデータソースは常に `output/model/views/` のみ
- normalized データを直接使いたい場合はパススルークエリを定義する（[queries-spec.md](../composer/queries-spec.md) 参照）

## ファイル構成

`presentation/templates/` 配下に配置する。

```
presentation/templates/
  root.md.jinja2             # エントリポイント（必須）
  erd.md.jinja2              # パーシャル
  entity-detail.md.jinja2    # パーシャル
  mermaid-er.mermaid.jinja2  # パーシャル（Mermaid エスケープ）
```

## root テンプレート

ユーザが必ず書くエントリポイント。ドキュメント全体の構成を定義する:

```jinja2
{# templates/root.md.jinja2 #}
# システム要件定義書

{% section "erd" for views.erd %}
{% section "screen" for views.screen %}
{% section "usecase" for views.usecase %}
```

読者や目的が異なる場合は root テンプレートを分ける（社内向け、顧客向け等）。

## `{% section %}` カスタムタグ

`{% section %}` は描画をパーシャルテンプレートに委譲する。paging 設定に応じた分割/インライン判定については [paging-spec.md](paging-spec.md) を参照。

```jinja2
{# templates/erd.md.jinja2 #}
# {{ entry.title }}

{% section "entity-detail" for entry.entity %}
{% section "mermaid-er" with entry.relation %}
```

anchor と section は直交する概念:
- anchor（`key` 属性）: リンク可能かどうか（[anchor-spec.md](anchor-spec.md) 参照）
- section: 描画を委譲するかどうか

## パーシャルテンプレートとエスケープ

パーシャル単位で出力フォーマットが決まり、拡張子でエスケープモードを判定する:

| 拡張子 | エスケープモード |
|---|---|
| `.md.jinja2` | Markdown エスケープ |
| `.mermaid.jinja2` | Mermaid エスケープ |

## YAML 内の Markdown

description 等の長文フィールドには YAML のリテラルブロックを使用:

```yaml
entities:
  - id: user
    name: ユーザー
    description: |
      システムを利用する人物を表す。

      - `email`: ログインIDとしても使用
      - `status`: 有効/無効/仮登録の3状態
```

**注意**: description 内に見出し（`##`）を使う場合、テンプレート側で見出しレベルが競合しないよう設計が必要。複雑な構造はスキーマで表現することを推奨。

## 標準テンプレート

アプリは以下の標準テンプレートを提供（ユーザはコピーしてカスタマイズ可能）:

- ER図（Mermaid）
- DFD（Mermaid）
- CRUD マトリクス表

標準テンプレートと同名のファイルをユーザの `presentation/templates/` に置くとオーバーライドできる。
