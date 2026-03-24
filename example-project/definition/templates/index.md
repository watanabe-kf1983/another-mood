# システム設計ドキュメント

## エンティティ一覧

{%- for entity in entities %}
- [{{ entity.name }}](entity-detail/{{ entity.id }}.md)
{%- endfor %}

{%- for entity in entities -%}
{% section "entity-detail" with entity %}
{%- endfor %}

## ER図（カテゴリ別）

{%- for entry in erds %}
- [{{ entry.category }} の ER図](erd/{{ entry.id }}.md)
{%- endfor %}

{%- for entry in erds -%}
{% section "erd" with entry %}
{%- endfor %}

## リレーション一覧

| From | To | Cardinality | Description |
|------|-----|-------------|-------------|
{% for rel in relations -%}
| {{ rel.from }} | {{ rel.to }} | {{ rel.cardinality }} | {{ rel.description }} |
{% endfor %}
