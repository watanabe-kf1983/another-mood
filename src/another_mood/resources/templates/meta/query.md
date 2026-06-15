{% set entities = node("/__definition/entities") %}
{% macro mermaid_type_id(e) %}{{ e.item_type.id | replace(".", "_") | safe }}{% endmacro %}
# Query: {{ id }}

## Source Diagram

{% set node_ids = ([from] + (join | map(attribute='to') | list)) | unique | list %}
{% filter dedent %}
    ```mermaid
    classDiagram
    {% for entity in entities if entity.id in node_ids %}
        class {{ mermaid_type_id(entity) | safe }}["{{ entity.item_type.id | safe }}"]
    {% endfor %}
    {% for entity in entities if entity.id in node_ids and entity.parent_entity and entity.parent_entity in node_ids %}
        {% set parent = entities | child(entity.parent_entity) %}
        {{ mermaid_type_id(parent) | safe }} *-- {{ mermaid_type_id(entity) | safe }}
    {% endfor %}
    {% for top_id in node_ids %}
        {% set top_entity = entities | child(top_id) %}
        {% for entity in entities if entity.id == top_id or entity.id.startswith(top_id ~ ".") %}
            {% for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity in node_ids %}
                {% set target = entities | child(attr.x_ref.entity) %}
                {% set rel_path = "" if entity.id == top_id else entity.id[(top_id ~ ".") | length:] %}
                {% set label = (rel_path ~ "." ~ attr.id) if rel_path else attr.id %}
                {{ mermaid_type_id(top_entity) | safe }} --> {{ mermaid_type_id(target) | safe }} : {{ label | safe }}
            {% endfor %}
        {% endfor %}
    {% endfor %}
    ```
{% endfilter %}

## Definition

### From

[{{ from }}]({{ node("__meta_entity", from) | href }})

{% if flatten %}
### Flatten

| Of | As | Preserve Empty |
|----|----|----------------|
{% for entry in flatten %}
| {{ entry.of }} | {{ entry.as }} | {% if entry.preserve_empty %}yes{% endif %} |
{% endfor %}

{% endif %}
{% if join %}
### Join

| To | On (left = right) | As | Pre-join where | Flatten |
|----|-------------------|-----|----------------|---------|
{% for entry in join %}
    {{- "" }}| [{{ entry.to }}]({{ node("__meta_entity", entry.to) | href }})
    {{- "" }} | {{ entry.on.left }} = {{ entry.on.right }}
    {{- "" }} | {{ entry.as }}
    {{- "" }} | {% if entry.where %}{{ code_inline(entry.where | to_yaml(true)) }}{% endif %}
    {{- "" }} | {% if entry.flatten %}{{ code_inline(entry.flatten | to_yaml(true)) }}{% endif %}
    {{- "" }} |
{% endfor %}

{% endif %}
{% if where %}
### Where

{{ code_fenced(where | to_yaml, "yaml") }}

{% endif %}
{% if grouped %}
### Grouped by

{{ grouped.by }} (as {{ grouped.as }})

{% endif %}
### Select

{% if select %}
| Item | As |
|------|----|
{% for entry in select %}
| {{ entry.item }} | {{ entry.as }} |
{% endfor %}
{% else %}
(no select items defined)
{% endif %}

## Shape

{% for entity in entities if entity.view and (entity.id == id or entity.id.startswith(id ~ ".")) %}
### Type: {{ entity.item_type.id }}

{% if entity.item_type.attributes %}
| id | type | required | validation | metadata |
|----|------|----------|------------|----------|
{% for attr in entity.item_type.attributes %}
    {% set array_suffix = "[]" if attr.child_item_type and attr.type.endswith("[]") else "" %}
    {{- "" }}| {{ code_inline(attr.id) }}
    {{- "" }} | {{ code_inline((attr.child_item_type or attr.type) ~ array_suffix) }}
    {{- "" }} | {% if attr.required %}yes{% endif %}
    {{- "" }} | {% if attr.validation %}{{ code_inline(attr.validation | to_yaml(true)) }}{% endif %}
    {{- "" }} | {% if attr.metadata %}{{ code_inline(attr.metadata | to_yaml(true)) }}{% endif %}
    {{- "" }} |
{% endfor %}
{% else %}
(no attributes)
{% endif %}

{% endfor %}
## Results

{% for entity in entities if entity.view and (entity.id == id or entity.id.startswith(id ~ ".")) %}
### {{ entity.id }}

{% mood_view "_table.md" with entity %}

{% endfor %}
