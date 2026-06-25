{% set entities = node(path="/__definition/entities") %}
{% macro mermaid_type_id(e) %}{{ e.item_type.id | replace(".", "_") | safe }}{% endmacro %}
# Entity Definition: {{ id }}{% if builtin %} (built-in){% endif +%}

[→ Entity Data]({{ node("__entity_data", id) | href }})

## Type Diagram

{% set ns = namespace(subtree_ids=[], fk_target_ids=[]) %}
{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") %}
    {% set ns.subtree_ids = ns.subtree_ids + [entity.id] %}
{% endfor %}
{% for entity in entities if entity.id in ns.subtree_ids %}
    {% for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity not in ns.subtree_ids and attr.x_ref.entity not in ns.fk_target_ids %}
        {% set ns.fk_target_ids = ns.fk_target_ids + [attr.x_ref.entity] %}
    {% endfor %}
{% endfor %}
{% filter dedent %}
    ```mermaid
    classDiagram
    {% for entity in entities if entity.id in ns.subtree_ids %}
        class {{ mermaid_type_id(entity) | safe }}["{{ entity.item_type.id | safe }}"] {
        {% for attr in entity.item_type.attributes %}
            {% set array_suffix = "[]" if attr.child_item_type and attr.type.endswith("[]") else "" %}
            {{ "  " }}{% if attr.required %}*{% endif %}{{ attr.id | safe }} : {{ ((attr.child_item_type or attr.type) ~ array_suffix) | safe }}{% if attr.x_ref %} [FK]{% endif +%}
        {% endfor %}
        }
    {% endfor %}
    {% for entity in entities if entity.id in ns.fk_target_ids %}
        class {{ mermaid_type_id(entity) | safe }}["{{ entity.item_type.id | safe }}"]
    {% endfor %}
    {% set draw_ids = ns.subtree_ids + ns.fk_target_ids %}
    {% for entity in entities if entity.id in ns.subtree_ids and entity.parent_entity and entity.parent_entity in draw_ids %}
        {% set parent = entities | child(entity.parent_entity) %}
        {{ mermaid_type_id(parent) | safe }} *-- {{ mermaid_type_id(entity) | safe }}
    {% endfor %}
    {% for entity in entities if entity.id in ns.subtree_ids %}
        {% for attr in entity.item_type.attributes if attr.x_ref %}
            {% set target = entities | child(attr.x_ref.entity) %}
            {{ mermaid_type_id(entity) | safe }} --> {{ mermaid_type_id(target) | safe }} : {{ attr.id | safe }}
        {% endfor %}
    {% endfor %}
    ```
{% endfilter %}

{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") %}
## Type: {{ entity.item_type.id }}

{% if entity.item_type.metadata %}
### metadata

{{ code_fenced(entity.item_type.metadata | to_yaml, "yaml") }}

{% endif %}
### attributes

{% if entity.item_type.attributes %}
| id | type | required | references | validation | metadata |
|----|------|----------|------------|------------|----------|
{% for attr in entity.item_type.attributes %}
    {% set array_suffix = "[]" if attr.child_item_type and attr.type.endswith("[]") else "" %}
    {% set xr = attr.x_ref %}
    {{- "" }}| {{ code_inline(attr.id) }}
    {{- "" }} | {{ code_inline((attr.child_item_type or attr.type) ~ array_suffix) }}
    {{- "" }} | {% if attr.required %}yes{% endif %}
    {{- "" }} | {% if xr %}[{{ code_inline(xr.entity ~ "." ~ xr.attribute) }}]({{ node("__entity_defs", xr.entity) | href }}){% endif %}
    {{- "" }} | {% if attr.validation %}{{ code_inline(attr.validation | to_yaml(true)) }}{% endif %}
    {{- "" }} | {% if attr.metadata %}{{ code_inline(attr.metadata | to_yaml(true)) }}{% endif %}
    {{- "" }} |
{% endfor %}
{% else %}
(no attributes defined yet)
{% endif %}

{% endfor %}
