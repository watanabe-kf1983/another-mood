{% set ordered = prose | sort(attribute="order_key") %}
{% set root = ordered | selectattr("depth", "equalto", 1) | first %}
{% set chapters = ordered | rejectattr("depth", "equalto", 1) | list %}
{% mood_view "prose.md" with root %}

## 目次

{% for record in chapters %}
{{ "  " * (record.depth - 2) }}- {{ record | link }}
{% endfor %}
- {{ node(path="/tasks") | link("タスクカタログ") }}
- {{ node(path="/roadmap") | link("ロードマップ") }}

{% for record in chapters %}
{% filter under_heading("#" * (record.depth - 1)) %}
{% mood_view "prose.md" with record %}
{% endfilter %}

{% endfor %}
{% filter under_heading("#") %}
{% mood_view "tasks.md" with tasks %}
{% endfilter %}

{% filter under_heading("#") %}
{% mood_view "roadmap.md" with roadmap %}
{% endfilter %}
