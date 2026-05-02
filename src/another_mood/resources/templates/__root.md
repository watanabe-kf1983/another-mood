# Another Mood

{% set entity_roots = __definition.entities | rejectattr('view') | rejectattr('parent_entity') | list %}
## Entities

{% if entity_roots -%}
{% for entity in entity_roots | sort(attribute='builtin') -%}
- [{{ entity.id }}](__meta_entity/{{ entity.id }}.md){% if entity.builtin %} (built-in){% endif %}{% if entity.item_type.metadata.title %} — {{ entity.item_type.metadata.title }}{% endif %}
{% endfor %}
{% for entity in entity_roots -%}
{% mood_view "__meta_entity" with {
  "id": entity.id,
  "builtin": entity.builtin,
  "entities": __definition.entities,
} %}
{%- endfor %}
{% for entity in entity_roots -%}
{% mood_view "__table_view" with {
  "id": entity.id,
  "entities": __definition.entities,
  "__views": __views,
} %}
{%- endfor %}
{%- else -%}
(no entities defined yet)
{%- endif %}

## Queries

{% if __definition.queries -%}
{% for query in __definition.queries -%}
- [{{ query.id }}](__meta_query/{{ query.id }}.md)
{% endfor %}
{% for query in __definition.queries -%}
{% mood_view "__meta_query" with {
  "id": query.id,
  "from": query.from,
  "grouped": query.grouped,
  "select": query.select,
  "entities": __definition.entities,
  "__views": __views,
} %}
{%- endfor %}
{%- else -%}
(no queries defined yet)
{%- endif %}

## Reports

[→ reports/](reports/)
