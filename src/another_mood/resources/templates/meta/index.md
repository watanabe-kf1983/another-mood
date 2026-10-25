{% set entities = node(path="/__definition/entities") %}
{% macro mermaid_type_id(e) %}{{ e.item_type.id | replace(".", "_") | safe }}{% endmacro %}
# Database Information

## Entity Relationships

{# `prose` is always a built-in top-level entity, so __defs.entity_tree /
   __defs.entities are never empty — no empty-state branch here (cf. ## Views, which keeps
   one: user views can be absent). #}
{% filter dedent %}
    ```mermaid
    classDiagram
    {% for entity in __defs.entity_tree %}
        class {{ mermaid_type_id(entity) | safe }}["{{ entity.item_type.id | safe }}"]
    {% endfor %}
    {% set node_ids = __defs.entity_tree | map(attribute='id') | list %}
    {# The root entity is not a node: top-level entities draw no edge to it. #}
    {% for entity in __defs.entity_tree if entity.parent_entity in node_ids %}
        {% set parent = entities | child(entity.parent_entity) %}
        {{ mermaid_type_id(parent) | safe }} *-- {{ mermaid_type_id(entity) | safe }}
    {% endfor %}
    {% for entity in __defs.entity_tree %}
        {% for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity in node_ids %}
            {% set target = entities | child(attr.x_ref.entity) %}
            {{ mermaid_type_id(entity) | safe }} --> {{ mermaid_type_id(target) | safe }} : {{ attr.id | safe }}
        {% endfor %}
    {% endfor %}
    ```
{% endfilter %}

## Entities

{# never empty: `prose` is always a built-in top-level entity (see ## Entity Relationships). #}
{% filter dedent %}
    {% for entity in __defs.entities %}
        - {{ entity | link }}{% if entity.builtin %} (built-in){% endif %}{% if entity.metadata.title %} — {{ entity.metadata.title }}{% endif +%}
    {% endfor %}
    {% for entity in __defs.entities %}
        {{- entity | render("entity_def.md") -}}
    {% endfor %}
{% endfilter %}

## Views

{% if __defs.views %}
{% filter dedent %}
    {% for view in __defs.views %}
        - {{ view | link }}
    {% endfor %}
    {% for view in __defs.views %}
        {{- view | render("view_def.md") -}}
    {% endfor %}
{% endfilter %}
{% else %}
(no views defined yet)
{% endif %}

{# Absent only without a catalog root entity (a bare data tree). #}
{% if __defs.root %}
## Attributes

- {{ __defs.root | link("Attributes") }}
{{ __defs.root | render("root_def.md") }}
{% endif %}
{# Data pages for the root and every top-level source; each render splits
   to its own page, so nothing shows inline. #}
{% if __data.root %}{{ __data.root | render("root_data.md") }}{% endif %}
{% filter dedent %}
    {% for entity in __data.entities %}
        {{- entity | render("entity_data.md") -}}
    {% endfor %}
    {% for view in __data.views %}
        {{- view | render("view_data.md") -}}
    {% endfor %}
{% endfilter %}
