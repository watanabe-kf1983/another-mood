# システム設計ドキュメント

## エンティティ一覧

{%- for entity in entities -%}
{% section "entity-detail" with entity %}
{%- endfor %}

## リレーション一覧

| From | To | Cardinality | Description |
|------|-----|-------------|-------------|
{% for rel in relations -%}
| {{ rel.from }} | {{ rel.to }} | {{ rel.cardinality }} | {{ rel.description }} |
{% endfor %}
