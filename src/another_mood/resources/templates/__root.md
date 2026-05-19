# Another Mood

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
