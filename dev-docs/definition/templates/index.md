[Documentation](prose/index.md)

{%- for record in prose -%}
{% section "prose" with record %}
{%- endfor %}

{% set dc = {"entities": entities, "references": references} %}
{% section "data-catalog" with dc %}

{% set tc = {"categories": categories} %}
{% section "tasks" with tc %}

{% set rm = {"tasks_by_phase": tasks_by_phase} %}
{% section "roadmap" with rm %}
