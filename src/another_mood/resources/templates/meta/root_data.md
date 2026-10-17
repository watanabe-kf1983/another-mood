{# ``this`` is the whole __root_data result: one item, naming the root entity. #}
{% set entities = node(path="/__definition/entities") %}
{% set root_entity = entities | child((this | first).id) %}
{% set root = node(path="/") %}
# Attributes: Data

[← Attributes]({{ node("__root_def") | href }})

{# Collections are left out, as on the definition page: each has its own
   Data page.  A singleton has no value of its own; its scalars follow it
   as dotted attributes. #}
{% set attributes = root_entity.item_type.attributes
    | rejectattr('child_entity')
    | rejectattr('id', 'startingwith', '__')
    | rejectattr('type', 'equalto', 'object')
    | list %}
{% if attributes %}
| attribute | value |
|-----------|-------|
{% for attr in attributes %}
| {{ code_inline(attr.id) }} | {{ root | pluck(attr.id) | in_cell }} |
{% endfor %}
{% else %}
(no attributes)
{% endif %}
