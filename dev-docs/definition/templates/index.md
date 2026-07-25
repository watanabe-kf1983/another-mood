{% set ordered = prose | sort(attribute="order_key") %}
{% set root = ordered | selectattr("depth", "equalto", 1) | first %}
{% set chapters = ordered | rejectattr("depth", "equalto", 1) | list %}
{{- root | render("prose.md") }}

## 目次

{% for record in chapters %}
{{ "  " * (record.depth - 2) }}- {{ record | link }}
{% endfor %}
- {{ node(path="/tasks") | link("タスクカタログ") }}
- {{ node(path="/roadmap") | link("ロードマップ") }}

{% for record in chapters %}
{{- record | render("prose.md") | under_heading("#" * (record.depth - 1)) }}
{% endfor %}
{{- tasks | render("tasks.md") | under_heading("#") }}

{{ roadmap | render("roadmap.md") | under_heading("#") }}
