# {{ id }} — Data

[← Schema](../__meta_entity/{{ id }}.md)

{% if rows -%}
| {% for attribute in attributes %}{{ attribute.id }} | {% endfor %}
|{% for attribute in attributes %}---|{% endfor %}
{% for row in rows -%}
| {% for attribute in attributes -%}
{%- if attribute.entity -%}
[{{ (row[attribute.id] or []) | length }} items](../__table_view/{{ attribute.entity }}.md)
{%- else -%}
{{ row | at(attribute.id) | replace("|", "\|") | replace("\n", "<br>") }}
{%- endif %} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}
