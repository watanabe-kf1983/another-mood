# Another Mood

## Entity Relationships

{% if __user_content_entities -%}
```mermaid
classDiagram
{% for entity in __user_content_entities -%}
class {{ entity.item_type.id | mermaid_class_id }}["{{ entity.item_type.id }}"]
{% endfor -%}
{% for entity in __user_content_entities if entity.parent_entity -%}
{%- set parent = __user_content_entities | selectattr('id', 'eq', entity.parent_entity) | first -%}
{{ parent.item_type.id | mermaid_class_id }} *-- {{ entity.item_type.id | mermaid_class_id }}
{% endfor -%}
{% set node_ids = __user_content_entities | map(attribute='id') | list -%}
{% for entity in __user_content_entities -%}
{% for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity in node_ids -%}
{%- set target = __user_content_entities | selectattr('id', 'eq', attr.x_ref.entity) | first -%}
{{ entity.item_type.id | mermaid_class_id }} --> {{ target.item_type.id | mermaid_class_id }} : {{ attr.id }}
{% endfor -%}
{% endfor -%}
```
{%- else -%}
(no entities defined yet)
{%- endif %}

## Entities

{% if __user_entity_roots -%}
{% for entity in __user_entity_roots -%}
- [{{ entity.id }}](__meta_entity/{{ entity.id }}.md){% if entity.builtin %} (built-in){% endif %}{% if entity.item_type.metadata.title %} — {{ entity.item_type.metadata.title }}{% endif %}
{% endfor %}
{%- else -%}
(no entities defined yet)
{%- endif %}
{% for entity in __entity_roots -%}
{% mood_view "__meta_entity" with {
  "id": entity.id,
  "builtin": entity.builtin,
  "entities": __definition.entities,
} %}
{%- endfor %}
{% for entity in __entity_roots -%}
{% mood_view "__table_view" with {
  "id": entity.id,
  "entities": __definition.entities,
  "__views": __views,
} %}
{%- endfor %}

## Queries

{% if __user_queries -%}
{% for query in __user_queries -%}
- [{{ query.id }}](__meta_query/{{ query.id }}.md)
{% endfor %}
{%- else -%}
(no queries defined yet)
{%- endif %}
{% for query in __definition.queries -%}
{% mood_view "__meta_query" with {
  "id": query.id,
  "from": query.from,
  "flatten": query.flatten,
  "join": query.join,
  "where": query.where,
  "grouped": query.grouped,
  "select": query.select,
  "entities": __definition.entities,
  "__views": __views,
} %}
{%- endfor %}

## Reports

[→ reports/](reports/)
