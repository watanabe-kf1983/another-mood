# Query: {{ id }}

## Definition

### From

{{ from }}

{% if flatten -%}
### Flatten

{% if flatten is string or flatten is mapping -%}
{% set entries = [flatten] -%}
{% else -%}
{% set entries = flatten -%}
{% endif -%}
| Of | As | Preserve Empty |
|----|----|----------------|
{% for raw in entries -%}
{% set entry = {"of": raw, "as": raw} if raw is string else raw -%}
| {{ entry.of }} | {{ entry.as or entry.of }} | {% if entry.preserve_empty %}yes{% endif %} |
{% endfor %}

{% endif -%}
{% if where -%}
### Where

```yaml
{{ where | to_yaml }}
```

{% endif -%}
{% if grouped -%}
### Grouped by

{{ grouped.by }}{% if grouped.as %} (as {{ grouped.as }}){% endif %}

{% endif -%}
### Select

{% if select -%}
| Item | As |
|------|----|
{% for entry in select -%}
| {{ entry.item }} | {{ entry.as or entry.item }} |
{% endfor -%}
{%- else -%}
(no select items defined)
{%- endif %}

## Shape

{% for entity in entities if entity.view and (entity.id == id or entity.id.startswith(id ~ ".")) -%}
### Type: {{ entity.item_type.id }}

{% if entity.item_type.attributes -%}
| id | type | required | metadata | validation |
|----|------|----------|----------|------------|
{% for attribute in entity.item_type.attributes -%}
{%- set array_suffix = "[]" if attribute.item_type and attribute.type.endswith("[]") else "" -%}
{%- set type_cell = "`" ~ (attribute.item_type or attribute.type) ~ array_suffix ~ "`" -%}
| `{{ attribute.id }}` | {{ type_cell }} | {% if attribute.required %}yes{% endif %} | {% if attribute.metadata %}`{{ attribute.metadata | to_yaml(true) }}`{% endif %} | {% if attribute.validation %}`{{ attribute.validation | to_yaml(true) }}`{% endif %} |
{% endfor -%}
{%- else -%}
(no attributes)
{%- endif %}

{% endfor -%}
## Results

{% for entity in entities if entity.view and (entity.id == id or entity.id.startswith(id ~ ".")) -%}
### {{ entity.id }}

{% set rows = __views | walk_entity(entity.id, entities) -%}
{% set attributes = entity.item_type.attributes | rejectattr('type', 'equalto', 'object') | list -%}
{% if rows -%}
| {% for attribute in attributes %}{{ attribute.id }} | {% endfor %}
|{% for attribute in attributes %}---|{% endfor %}
{% for row in rows -%}
| {% for attribute in attributes -%}
{%- if attribute.entity -%}
*{{ (row | pluck(attribute.id) or []) | length }} items*
{%- else -%}
{{ row | pluck(attribute.id) | replace("|", "\|") | replace("\n", "<br>") }}
{%- endif %} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}

{% endfor -%}
