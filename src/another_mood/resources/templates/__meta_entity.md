# {{ id }}{% if builtin %} (built-in){% endif %}

[→ Data](../__table_view/{{ id }}.md)

{% if parent_entity -%}
Parent: [{{ parent_entity }}]({{ parent_entity }}.md)
{% endif -%}
{% if metadata.title %}
**{{ metadata.title }}**
{% endif -%}
{% if metadata.description %}
{{ metadata.description }}
{% endif %}
## Attributes

{% if attributes -%}
| ID | Type | Required | Title | Description |
|----|------|----------|-------|-------------|
{% for attribute in attributes -%}
{%- set type_cell = "[" ~ attribute.type ~ "](" ~ attribute.child_entity ~ ".md)" if attribute.child_entity else attribute.type -%}
{%- set required_cell = "yes" if attribute.required else "" -%}
| {{ attribute.id }} | {{ type_cell }} | {{ required_cell }} | {{ attribute.metadata.title }} | {{ attribute.metadata.description }} |
{% endfor -%}
{%- else -%}
(no attributes defined yet)
{%- endif %}
