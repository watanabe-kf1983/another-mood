# Entity Data: {{ id }}

[← Entity Definition](../__meta_entity/{{ id | as_url }}.md)

{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") -%}
## {{ entity.id }}

{% set rows = __views | walk_entity(entity.id, entities) -%}
{% set attributes = entity.item_type.attributes | rejectattr('type', 'equalto', 'object') | list -%}
{% set show_parent = entity.parent_entity -%}
{% if rows -%}
| {% if show_parent %}_parent_record | {% endif %}{% for attribute in attributes %}{{ attribute.id }} | {% endfor %}
|{% if show_parent %}---|{% endif %}{% for attribute in attributes %}---|{% endfor %}
{% for row in rows -%}
| {% if show_parent %}{{ row._parent_record.id | in_cell }} | {% endif %}{% for attribute in attributes -%}
{%- if attribute.child_entity -%}
*{{ (row | pluck(attribute.id) or []) | length }} items*
{%- else -%}
{{ row | pluck(attribute.id) | in_cell }}
{%- endif %} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}

{% endfor -%}
