# {{ id }}

{% if parent_entity -%}
Parent: [{{ parent_entity }}]({{ parent_entity }}.md)
{% endif -%}
{% if metadata and metadata.title %}
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
{%- set type_cell = "[" ~ field.type ~ "](" ~ field.child_entity ~ ".md)" if field.child_entity else field.type -%}
{%- set required_cell = "yes" if field.required else "" -%}
{%- set title_cell = field.metadata.title if field.metadata else "" -%}
{%- set desc_cell = field.metadata.description if field.metadata else "" -%}
| {{ field.id }} | {{ type_cell }} | {{ required_cell }} | {{ title_cell }} | {{ desc_cell }} |
{% endfor -%}
{%- else -%}
（フィールドはまだ定義されていません）
{%- endif %}
