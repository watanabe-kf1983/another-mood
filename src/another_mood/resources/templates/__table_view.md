# {{ id }} — Data

[← Schema](../__meta_entity/{{ id }}.md)

{% if rows -%}
| {% for field in fields %}{{ field.id }} | {% endfor %}
|{% for field in fields %}---|{% endfor %}
{% for row in rows -%}
| {% for field in fields -%}
{%- if field.child_entity -%}
[{{ (row[field.id] or []) | length }} items](../__table_view/{{ field.child_entity }}.md)
{%- else -%}
{{ row | at(field.id) | replace("|", "\|") | replace("\n", "<br>") }}
{%- endif %} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}
