# システム設計ドキュメント

## エンティティ一覧

{%- for entity in entities %}
- [{{ entity.name }}](entity-detail/{{ entity.id }}.md)
{%- endfor %}

{%- for entity in entities -%}
{% mood_view "entity-detail" with entity %}
{%- endfor %}

## ER図（カテゴリ別）

{%- for entry in erds %}
- [{{ entry.category }} の ER図](erd/{{ entry.id }}.md)
{%- endfor %}

{%- for entry in erds -%}
{% mood_view "erd" with entry %}
{%- endfor %}

{%- for record in prose -%}
{% mood_view "prose" with record %}
{%- endfor %}

## リレーション一覧

| From | To | Cardinality | Description |
|------|-----|-------------|-------------|
{% for rel in relations -%}
| {{ rel.from }} | {{ rel.to }} | {{ rel.cardinality }} | {{ rel.description }} |
{% endfor %}

## 全フィールド一覧

| Entity | Field | Type | PK | FK |
|--------|-------|------|----|----|
{% for row in entity_fields -%}
| {{ row.entity_name }} | {{ row.field.name }} | {{ row.field.type }} | {{ "✓" if row.field.pk else "" }} | {{ row.field.fk or "" }} |
{% endfor %}
