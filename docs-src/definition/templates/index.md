[Documentation](prose/index.md)

{%- for record in prose -%}
{% section "prose" with record %}
{%- endfor %}

{% set dc = {"entities": entities, "references": references} %}
{% section "data-catalog" with dc %}

{% set p8 = {"phase8_categories": phase8_categories} %}
{% section "phase8-tasks" with p8 %}
