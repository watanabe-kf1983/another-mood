[Documentation](prose/index.md)

{%- for record in prose -%}
{% section "prose" with record %}
{%- endfor %}

{% set dc = {"entities": entities, "references": references} %}
{% section "data-catalog" with dc %}
