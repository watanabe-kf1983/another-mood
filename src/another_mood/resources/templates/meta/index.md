{% set entities = node(path="/__definition/entities") %}
{% macro mermaid_type_id(e) %}{{ e.item_type.id | replace(".", "_") | safe }}{% endmacro %}
# Database Information

## Entity Relationships

{# `prose` is always a built-in root entity, so __entity_tree / __entity_defs
   are never empty — no empty-state branch here (cf. ## Views, which keeps
   one: user views can be absent). #}
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

## Entities

{# never empty: `prose` is always a built-in root entity (see ## Entity Relationships). #}
{% filter dedent %}
    {% for entity in __entity_defs %}
        - {{ entity | link }}{% if entity.builtin %} (built-in){% endif %}{% if entity.item_type.metadata.title %} — {{ entity.item_type.metadata.title }}{% endif +%}
    {% endfor %}
    {% for entity in __entity_defs %}
        {{- entity | render("entity_def.md") -}}
    {% endfor %}
{% endfilter %}

## Views

{% if __view_defs %}
{% filter dedent %}
    {% for view in __view_defs %}
        - {{ view | link }}
    {% endfor %}
    {% for view in __view_defs %}
        {{- view | render("view_def.md") -}}
    {% endfor %}
{% endfilter %}
{% else %}
(no views defined yet)
{% endif %}
{# Data pages for every root source, entities and views alike; each
   render splits to its own /__data/{id} page, so nothing shows inline. #}
{% filter dedent %}
    {% for source in __data %}
        {{- source | render("data.md") -}}
    {% endfor %}
{% endfilter %}
