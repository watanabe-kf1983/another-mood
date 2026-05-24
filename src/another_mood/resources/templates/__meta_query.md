# Query: {{ id }}

## Source Diagram

{% set node_ids = ([from] + (join | map(attribute='to') | list)) | unique | list -%}
```mermaid
classDiagram
{% for entity in entities if entity.id in node_ids -%}
class {{ entity.item_type.id | mermaid_class_id | safe }}["{{ entity.item_type.id | safe }}"]
{% endfor -%}
{% for entity in entities if entity.id in node_ids and entity.parent_entity and entity.parent_entity in node_ids -%}
{%- set parent = entities | selectattr('id', 'eq', entity.parent_entity) | first -%}
{{ parent.item_type.id | mermaid_class_id | safe }} *-- {{ entity.item_type.id | mermaid_class_id | safe }}
{% endfor -%}
{% for top_id in node_ids -%}
{%- set top_entity = entities | selectattr('id', 'eq', top_id) | first -%}
{% if top_entity -%}
{%- for entity in entities if entity.id == top_id or entity.id.startswith(top_id ~ ".") -%}
{%- for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity in node_ids -%}
{%- set target = entities | selectattr('id', 'eq', attr.x_ref.entity) | first -%}
{% if target -%}
{%- set rel_path = "" if entity.id == top_id else entity.id[(top_id ~ ".") | length:] -%}
{%- set label = (rel_path ~ "." ~ attr.id) if rel_path else attr.id -%}
{{ top_entity.item_type.id | mermaid_class_id | safe }} --> {{ target.item_type.id | mermaid_class_id | safe }} : {{ label | safe }}
{% endif -%}
{%- endfor -%}
{%- endfor -%}
{% endif -%}
{% endfor -%}
```

## Definition

### From

[{{ from }}](../__meta_entity/{{ from }}.md)

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
| [{{ entry.to }}](../__meta_entity/{{ entry.to }}.md) | {{ entry.on.left }} = {{ entry.on.right }} | {{ entry.as }} | {% if entry.where %}`{{ entry.where | to_yaml(true) | safe }}`{% endif %} | {% if entry.flatten %}`{{ entry.flatten | to_yaml(true) | safe }}`{% endif %} |
{% endfor %}

{% endif -%}
{% if where -%}
### Where

```yaml
{{ where | to_yaml | safe }}
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
| id | type | required | validation | metadata |
|----|------|----------|------------|----------|
{% for attribute in entity.item_type.attributes -%}
{%- set array_suffix = "[]" if attribute.child_item_type and attribute.type.endswith("[]") else "" -%}
{%- set type_cell = "`" ~ (attribute.child_item_type or attribute.type) ~ array_suffix ~ "`" -%}
| `{{ attribute.id | safe }}` | {{ type_cell | safe }} | {% if attribute.required %}yes{% endif %} | {% if attribute.validation %}`{{ attribute.validation | to_yaml(true) | safe }}`{% endif %} | {% if attribute.metadata %}`{{ attribute.metadata | to_yaml(true) | safe }}`{% endif %} |
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
{%- if attribute.child_entity -%}
*{{ (row | pluck(attribute.id) or []) | length }} items*
{%- else -%}
{{ row | pluck(attribute.id) | replace("\n", " ") }}
{%- endif %} | {% endfor %}
{% endfor -%}
{%- else -%}
(no records)
{%- endif %}

{% endfor -%}
