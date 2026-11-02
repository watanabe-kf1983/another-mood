{% set ordered = prose | sort(attribute="order_key") %}
{% set root = ordered | selectattr("depth", "equalto", 1) | first %}
{% set chapters = ordered | rejectattr("depth", "equalto", 1) | list %}
{{- root | render("prose.md") }}

## 目次

{% for record in chapters %}
{{ "  " * (record.depth - 2) }}- {{ record | link }}
{% endfor %}

{% for record in chapters %}
  {{- record | render("prose.md") | under_heading("#" * (record.depth - 1)) }}
{% endfor %}
