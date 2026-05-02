# Another Mood

## Definitions

### Entities

{% if __definition.entities -%}
{% for entity in __definition.entities | sort(attribute='builtin') -%}
- [{{ entity.id }}](__meta_entity/{{ entity.id }}.md){% if entity.builtin %} (built-in){% endif %}{% if entity.item_type.metadata.title %} — {{ entity.item_type.metadata.title }}{% endif %}
{% endfor %}
{% for entity in __definition.entities -%}
{% mood_view "__meta_entity" with entity %}
{%- endfor %}
{% for entity in __definition.entities -%}
{% mood_view "__table_view" with {"id": entity.id, "attributes": entity.item_type.attributes, "rows": __views | query_from(entity.id)} %}
{%- endfor %}
{%- else -%}
(no entities defined yet)
{%- endif %}

### Queries

{% if __definition.queries -%}
{% for query in __definition.queries -%}
- [{{ query.id }}](__meta_query/{{ query.id }}.md) — from {{ query.from }}
{% endfor %}
{% for query in __definition.queries -%}
{% mood_view "__meta_query" with query %}
{%- endfor %}
{%- else -%}
(no queries defined yet)
{%- endif %}

## Reports

[→ reports/](reports/)
