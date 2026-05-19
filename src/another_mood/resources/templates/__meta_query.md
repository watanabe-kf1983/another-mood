# Query: {{ id }}

## Definition

### From

{{ from }}

{% if flatten -%}
### Flatten

| Of | As | Preserve Empty |
|----|----|----------------|
{% for entry in flatten -%}
| {{ entry.of }} | {{ entry.as }} | {% if entry.preserve_empty %}yes{% endif %} |
{% endfor %}

{% endif -%}
{% if join -%}
### Join

| To | On (left = right) | As | Pre-join where | Flatten |
|----|-------------------|-----|----------------|---------|
{% for entry in join -%}
| {{ entry.to }} | {{ entry.on.left }} = {{ entry.on.right }} | {{ entry.as }} | {% if entry.where %}`{{ entry.where | to_yaml(true) }}`{% endif %} | {% if entry.flatten %}`{{ entry.flatten | to_yaml(true) }}`{% endif %} |
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

{{ grouped.by }} (as {{ grouped.as }})

{% endif -%}
### Select

{% if select -%}
| Item | As |
|------|----|
{% for entry in select -%}
| {{ entry.item }} | {{ entry.as }} |
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
