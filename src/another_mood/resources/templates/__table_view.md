# {{ id }} — Data

[← Schema](../__meta_entity/{{ id }}.md)

{% set shown = fields | rejectattr("child_entity") | list %}
{% if rows -%}
| {% for field in shown %}{{ field.id }} | {% endfor %}
|{% for field in shown %}---|{% endfor %}
{% for row in rows -%}
| {% for field in shown %}{{ row | at(field.id) | replace("|", "\|") | replace("\n", "<br>") }} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}
