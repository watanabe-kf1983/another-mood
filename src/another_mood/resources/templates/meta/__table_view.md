# Entity Data: {{ id }}

[← Entity Definition](../__meta_entity/{{ id | as_url }}.md)

{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") -%}
## {{ entity.id }}

{% set rows = __views | walk_entity(entity.id, entities) -%}
{% set attributes = entity.item_type.attributes | rejectattr('type', 'equalto', 'object') | list -%}
{% if rows -%}
| {% for attribute in attributes %}{{ attribute.id }} | {% endfor %}_anchor_id |
|{% for attribute in attributes %}---|{% endfor %}---|
{% for row in rows -%}
| {% for attribute in attributes -%}
{%- if attribute.child_entity -%}
*{{ (row | pluck(attribute.id) or []) | length }} items*
{%- else -%}
{{ row | pluck(attribute.id) | in_cell }}
{%- endif %} | {% endfor %}{{ row._meta.anchor_id | in_cell }} |
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}

{% endfor -%}
