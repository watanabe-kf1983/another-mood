[Documentation](prose/index.md)

{%- for record in prose -%}
{% mood_view "prose.md" with record %}
{%- endfor %}

{% set tc = {"categories": categories} %}
{% mood_view "tasks.md" with tc %}

{% set rm = {"tasks_by_phase": tasks_by_phase} %}
{% mood_view "roadmap.md" with rm %}
