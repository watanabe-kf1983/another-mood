# Template Specification

テンプレートの仕様。見た目（純粋な表示ロジック）を定義する。

## Pagination（複数ファイル生成）

コレクションの各要素から個別のファイルを生成する機能。
11ty-like なフロントマターで定義する。

```liquid
---
foreach: entities
path: "docs/entities/{{ id }}.md"
---
# {{ name }}

{{ description }}
```

## データアクセス

**JSONPath を統一的なクエリ構文として採用：**

- CLI からのクエリ: `reqs-builder query "$.entities[?@.type=='master']"`
- テンプレート内: `{{ source | jsonpath("$.relations[?@.from==entity.id]") }}`
- MCP API: 同じ JSONPath 構文

LiquidJS のネイティブ構文（`entity.name` 等）も使用可能だが、
複雑なフィルタリングには JSONPath を推奨。

## テンプレートのオーバライド

`templates/` ディレクトリにユーザ定義のテンプレートを配置：

```
templates/
  entity-detail.md        # ユーザ定義テンプレート
  er.md                   # 標準テンプレートをオーバーライド
```

- 標準テンプレートと同名のファイルを置くとオーバーライド
- 標準テンプレートをコピーして編集することを推奨

## YAML 内の Markdown

description 等の長文フィールドには YAML のリテラルブロックを使用：

```yaml
entities:
  - id: user
    name: ユーザー
    description: |
      システムを利用する人物を表す。

      - `email`: ログインIDとしても使用
      - `status`: 有効/無効/仮登録の3状態
```

**注意**: description 内に見出し（`##`）を使う場合、
テンプレート側で見出しレベルが競合しないよう設計が必要。
複雑な構造はスキーマで表現することを推奨。

## 標準テンプレート

アプリは以下の標準テンプレートを提供（ユーザはコピーしてカスタマイズ可能）：

- `er`: Mermaid ER図
- `dfd`: Mermaid/PlantUML DFD
- `crud-matrix`: CRUD マトリクス表
- （他、必要に応じて追加）

## ER図テンプレート実装例

### 前提となるデータ構造

```yaml
# source/entities.yaml
entities:
  - id: user
    name: ユーザー
    fields:
      - name: id
        type: string
        pk: true
      - name: email
        type: string
      - name: status
        type: string

  - id: order
    name: 注文
    fields:
      - name: id
        type: string
        pk: true
      - name: user_id
        type: string
        fk: user
      - name: total
        type: number
```

```yaml
# source/relations.yaml
relations:
  - from: user
    to: order
    cardinality: "1:N"
    label: "places"

  - from: order
    to: order_item
    cardinality: "1:N+"
    label: "contains"
```

### テンプレート（templates/er.md）

```liquid
```mermaid
erDiagram
{% for entity in nodes %}
    {{ entity.id }} {
{% for field in entity.fields %}
        {{ field.type }} {{ field.name }}{% if field.pk %} PK{% endif %}{% if field.fk %} FK{% endif %}

{% endfor %}
    }
{% endfor %}
{% for rel in edges %}
{% if rel.cardinality == "1:1" %}
    {{ rel.from }} ||--|| {{ rel.to }} : "{{ rel.label }}"
{% elif rel.cardinality == "1:N" %}
    {{ rel.from }} ||--o{ {{ rel.to }} : "{{ rel.label }}"
{% elif rel.cardinality == "1:N+" %}
    {{ rel.from }} ||--|{ {{ rel.to }} : "{{ rel.label }}"
{% elif rel.cardinality == "0..1:1" %}
    {{ rel.from }} |o--|| {{ rel.to }} : "{{ rel.label }}"
{% elif rel.cardinality == "0..1:N" %}
    {{ rel.from }} |o--o{ {{ rel.to }} : "{{ rel.label }}"
{% elif rel.cardinality == "N:N" %}
    {{ rel.from }} }o--o{ {{ rel.to }} : "{{ rel.label }}"
{% else %}
    {{ rel.from }} -- {{ rel.to }} : "{{ rel.label }}"
{% endif %}
{% endfor %}
```
```

### カーディナリティ対応表

| 値 | Mermaid記法 | 意味 |
|----|-------------|------|
| `1:1` | `\|\|--\|\|` | 1対1（両方必須） |
| `1:N` | `\|\|--o{` | 1対多（多側は0以上） |
| `1:N+` | `\|\|--\|{` | 1対多（多側は1以上） |
| `0..1:1` | `\|o--\|\|` | 0or1 対 1 |
| `0..1:N` | `\|o--o{` | 0or1 対 多 |
| `N:N` | `}o--o{` | 多対多 |

### 変換ロジックの方針

- **Phase 2**: テンプレート内の条件分岐（if/elif）で対応
  - カーディナリティのバリエーションは有限なので十分対処可能
  - 明示的で、ユーザがカスタマイズしやすい
- **将来の拡張**: Report 定義での mapping 機能
  - 同じマッピングを複数テンプレートで使いたい場合に検討
  - カスタムフィルタは最後の手段（プラグイン機構として設計）
