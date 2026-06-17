{% set entities = node("/__definition/entities") %}
{% macro mermaid_type_id(e) %}{{ e.item_type.id | replace(".", "_") | safe }}{% endmacro %}
# Another Mood

## Entity Relationships

{% if __entity_tree %}
{% filter dedent %}
    ```mermaid
    classDiagram
    {% for entity in __entity_tree %}
        class {{ mermaid_type_id(entity) | safe }}["{{ entity.item_type.id | safe }}"]
    {% endfor %}
    {% for entity in __entity_tree if entity.parent_entity %}
        {% set parent = entities | child(entity.parent_entity) %}
        {{ mermaid_type_id(parent) | safe }} *-- {{ mermaid_type_id(entity) | safe }}
    {% endfor %}
    {% set node_ids = __entity_tree | map(attribute='id') | list %}
    {% for entity in __entity_tree %}
        {% for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity in node_ids %}
            {% set target = entities | child(attr.x_ref.entity) %}
            {{ mermaid_type_id(entity) | safe }} --> {{ mermaid_type_id(target) | safe }} : {{ attr.id | safe }}
        {% endfor %}
    {% endfor %}
    ```
{% endfilter %}
{% else %}
(no entities defined yet)
{% endif %}

## Entities

{% if __entity_defs %}
{% for entity in __entity_defs %}
- [{{ entity.id }}]({{ node("__entity_defs", entity.id) | href }}){% if entity.builtin %} (built-in){% endif %}{% if entity.item_type.metadata.title %} — {{ entity.item_type.metadata.title }}{% endif +%}
{% endfor %}
{% else %}
(no entities defined yet)
{% endif %}
{% for entity in __entity_defs %}
{% mood_view "entity_def.md" with entity %}
{% endfor %}
{% for entity in __entity_data %}
{% mood_view "entity_data.md" with entity %}
{% endfor %}

## Queries

{% if __queries %}
{% for query in __queries %}
- [{{ query.id }}]({{ node("__queries", query.id) | href }})
{% endfor %}
{% else %}
(no queries defined yet)
{% endif %}
{% for query in __queries %}
{% mood_view "query.md" with query %}
{% endfor %}

## Reports

[→ reports/](reports/)
