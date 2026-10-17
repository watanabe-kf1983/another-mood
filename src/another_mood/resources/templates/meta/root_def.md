{# ``this`` is the whole __root_def result: one item, the root entity. #}
{% set root = this | first %}
# Attributes

The top-level singletons and scalars: the values that sit directly under the root, outside any collection.

[→ Data]({{ node("__root_data") | href }})

{% if root.metadata %}
## metadata

{{ code_fenced(root.metadata | to_yaml, "yaml") }}

{% endif %}
## attributes

{# Collections are left out: each has its own page under Entities.  So
   are catalog-internal attributes (``__definition``), like the
   catalog-internal entities elsewhere on ``__db/``. #}
{% set attributes = root.item_type.attributes
    | rejectattr('child_entity')
    | rejectattr('id', 'startingwith', '__')
    | list %}
{% if attributes %}
| id | type | required | references | validation | metadata |
|----|------|----------|------------|------------|----------|
{% for attr in attributes %}
    {% set xr = attr.x_ref %}
    {{- "" }}| {{ code_inline(attr.id) }}
    {{- "" }} | {{ code_inline(attr.type) }}
    {{- "" }} | {% if attr.required %}yes{% endif %}
    {{- "" }} | {% if xr %}[{{ code_inline(xr.entity ~ "." ~ xr.attribute) }}]({{ node("__entity_defs", xr.entity) | href }}){% endif %}
    {{- "" }} | {% if attr.validation %}{{ code_inline(attr.validation | to_yaml(true)) }}{% endif %}
    {{- "" }} | {% if attr.metadata %}{{ code_inline(attr.metadata | to_yaml(true)) }}{% endif %}
    {{- "" }} |
{% endfor %}
{% else %}
(no attributes defined yet)
{% endif %}
