# システム設計ドキュメント

## エンティティ一覧

{% for entity in entities -%}
- {{ entity.name }}
{% endfor %}
## リレーション一覧

| From | To | Cardinality |
|------|-----|-------------|
{% for rel in relations -%}
| {{ rel.from }} | {{ rel.to }} | {{ rel.cardinality }} |
{% endfor %}
