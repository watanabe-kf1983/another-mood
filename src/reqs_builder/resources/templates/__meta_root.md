# Meta Documentation

## Entities

{% if __definition is defined and __definition.entities -%}
{% for entity in __definition.entities -%}
- **{{ entity.id }}**{% if entity.metadata and entity.metadata.title %} — {{ entity.metadata.title }}{% endif %}
{% endfor -%}
{% else -%}
（エンティティはまだ定義されていません）
{% endif %}
