# {{ id }}{% if builtin %} (built-in){% endif %}

{% if parent_entity -%}
Parent: [{{ parent_entity }}]({{ parent_entity }}.md)
{% endif -%}
{% if metadata.title %}
**{{ metadata.title }}**
{% endif -%}
{% if metadata.description %}
{{ metadata.description }}
{% endif %}
## Fields

{% if fields -%}
| ID | Type | Required | Title | Description |
|----|------|----------|-------|-------------|
{% for field in fields -%}
{%- set type_cell = "[" ~ field.type ~ "](" ~ field.child_entity ~ ".md)" if field.child_entity else field.type -%}
{%- set required_cell = "yes" if field.required else "" -%}
| {{ field.id }} | {{ type_cell }} | {{ required_cell }} | {{ field.metadata.title }} | {{ field.metadata.description }} |
{% endfor -%}
{%- else -%}
(no fields defined yet)
{%- endif %}
