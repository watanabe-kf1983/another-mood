# {{ id }}

{% if metadata and metadata.title -%}
**{{ metadata.title }}**
{% endif -%}
{% if metadata and metadata.description %}
{{ metadata.description }}
{% endif %}
## Fields

{% if fields -%}
| ID | Type | Required | Title | Description |
|----|------|----------|-------|-------------|
{% for field in fields -%}
| {{ field.id }} | {{ field.type }} | {% if field.required %}yes{% endif %} | {{ field.metadata.title if field.metadata and field.metadata.title else "" }} | {{ field.metadata.description if field.metadata and field.metadata.description else "" }} |
{% endfor -%}
{%- else -%}
（フィールドはまだ定義されていません）
{%- endif %}
