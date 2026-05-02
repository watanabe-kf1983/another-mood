# Entity Data: {{ id }}

[← Entity Definition](../__meta_entity/{{ id }}.md)

{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") -%}
## {{ entity.id }}

{% set rows = __views | query_from(entity.id) -%}
{% if rows -%}
| {% for attribute in entity.item_type.attributes %}{{ attribute.id }} | {% endfor %}
|{% for attribute in entity.item_type.attributes %}---|{% endfor %}
{% for row in rows -%}
| {% for attribute in entity.item_type.attributes -%}
{%- if attribute.entity -%}
*{{ (row[attribute.id] or []) | length }} items*
{%- else -%}
{{ row | at(attribute.id) | replace("|", "\|") | replace("\n", "<br>") }}
{%- endif %} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}

{% endfor -%}
