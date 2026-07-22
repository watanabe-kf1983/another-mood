{# ``this`` is the entity id (a string), not the entity node: this table is
   parameterized by a schema entity but *draws* the entity's data rows, so the
   entity itself is never placed on this page.  Passing an id (re-looked-up
   here) keeps the subject a non-node, exempt from the render subtree guard
   -- the entity lives under /__definition, not under this page's subtree. #}
{% set entities = node(path="/__definition/entities") %}
{% set entity = entities | child(this) %}
# {{ entity.id }}

{% set root = node(path="/") %}
{% set rows = root | walk_entity(entity.id, entities) %}
{% set attributes = entity.item_type.attributes | rejectattr('type', 'equalto', 'object') | list %}
{% if rows %}
| {% for attribute in attributes %}{{ attribute.id }} | {% endfor %}_anchor_path |
|{% for attribute in attributes %}---|{% endfor %}---|
{% for row in rows %}
| {% for attribute in attributes -%}
    {%- if attribute.child_entity -%}
        *{{ (row | pluck(attribute.id) or []) | length }} items*
    {%- else -%}
        {{ row | pluck(attribute.id) | in_cell }}
    {%- endif %} | {% endfor %}{{ row._meta.anchor_path | in_cell }} |
{% endfor %}
{% else %}
(no records)
{% endif %}
