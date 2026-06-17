{% set entity = this %}
# {{ entity.id }}

{% set root = node("/") %}
{% set entities = node("/__definition/entities") %}
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
