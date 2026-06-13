{{ node("/prose/index") | link }}

{%- for record in prose -%}
{% mood_view "prose.md" with record %}
{%- endfor %}

{% mood_view "tasks.md" with tasks %}

{% mood_view "roadmap.md" with roadmap %}
