{% set entities = node("/__definition/entities") %}
{% macro mermaid_type_id(e) %}{{ e.item_type.id | replace(".", "_") | safe }}{% endmacro %}
# Another Mood

## Entity Relationships

{% if __user_content_entities %}
{% filter dedent %}
    ```mermaid
    classDiagram
    {% for entity in __user_content_entities %}
        class {{ mermaid_type_id(entity) | safe }}["{{ entity.item_type.id | safe }}"]
    {% endfor %}
    {% for entity in __user_content_entities if entity.parent_entity %}
        {% set parent = entities | child(entity.parent_entity) %}
        {{ mermaid_type_id(parent) | safe }} *-- {{ mermaid_type_id(entity) | safe }}
    {% endfor %}
    {% set node_ids = __user_content_entities | map(attribute='id') | list %}
    {% for entity in __user_content_entities %}
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

{% if __user_entity_roots %}
{% for entity in __user_entity_roots %}
- [{{ entity.id }}]({{ node("__meta_entity", entity.id) | href }}){% if entity.builtin %} (built-in){% endif %}{% if entity.item_type.metadata.title %} — {{ entity.item_type.metadata.title }}{% endif +%}
{% endfor %}
{% else %}
(no entities defined yet)
{% endif %}
{% for entity in __meta_entity %}
{% mood_view "entity_def.md" with entity %}
{% endfor %}
{% for entity in __table_view %}
{% mood_view "entity_data.md" with entity %}
{% endfor %}

## Queries

{% if __user_queries %}
{% for query in __user_queries %}
- [{{ query.id }}]({{ node("__meta_query", query.id) | href }})
{% endfor %}
{% else %}
(no queries defined yet)
{% endif %}
{% for query in __meta_query %}
{% mood_view "query.md" with query %}
{% endfor %}

## Reports

[→ reports/](reports/)
