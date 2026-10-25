{% set ordered = prose | sort(attribute="order_key") %}
{% set root = ordered | selectattr("depth", "equalto", 1) | first %}
{% set chapters = ordered | rejectattr("depth", "equalto", 1) | list %}
{#- The appendix is reached through links from the body, so the table of
    contents shows only its entrance; the entrance page lists the rest. -#}
{{- root | render("prose.md") }}

## 目次

{% for record in chapters if not record.id is startingwith("90-appendix/") or record.id == "90-appendix/index" %}
{{ "  " * (record.depth - 2) }}- {{ record | link }}
{% endfor %}
- {{ node(path="/tasks") | link("タスクカタログ") }}
- {{ node(path="/roadmap") | link("ロードマップ") }}

{% for record in chapters %}
  {{- record | render("appendix.md" if record.id == "90-appendix/index" else "prose.md") | under_heading("#" * (record.depth - 1)) }}
{% endfor %}
{{- tasks | render("tasks.md") | under_heading("#") }}

{{ roadmap | render("roadmap.md") | under_heading("#") }}
