# {{ this.name }} ({{ this.id }})

{{ this.description }}

{# The layout is the one item that cannot be derived, and the drawing (a blob)
   is embedded right under the description. A mismatch between the drawing and
   the table of input and output items is not detected by the build, so the
   table stays next to the drawing where the two can be compared by eye. #}
{% if this.layout %}
![Layout of the {{ this.name }}]({{ node(path="/blob/" ~ this.layout.figure) | href }})
  {% if this.layout.source %}

([Source of the layout]({{ node(path="/blob/" ~ this.layout.source) | href }}))
  {% endif %}
{% endif %}

| Item | Content |
|------|---------|
| Category | {{ this.category | capitalize }} |
| Use cases
  {{- "" }} | {% for u in this.use_cases %}{{ node("srs", "requirements", "functional", u.id) | link(u.id) }} {{ node("use_cases", u.id).name }}{% if not loop.last %}, {% endif %}{% else %}(none){% endfor %}
  {{- "" }} |

## Input and output items

{% if this.io_items %}
| Item | Direction | References | Description |
|------|-----------|------------|-------------|
  {# An x-ref can only name an entity ID, and ref.attribute is a bare string,
     so a misspelling still builds. Match it against the attributes of the
     referenced entity by name, and if absent mark the table so a reader
     notices. #}
  {% for i in this.io_items %}
    {% set dst = node("sdd", "data_design", "logical_data_model", i.ref.entity_id) if i.ref else none %}
    {{- "" }}| {{ i.name }}
    {{- "" }} | {{ i.direction | capitalize }}
    {{- "" }} | {% if i.ref %}{{ dst | link(dst.name) }}.{{ i.ref.attribute }}{% if i.ref.attribute not in dst.attributes | map(attribute="name") | list %} (no such attribute in the referenced entity){% endif %}{% endif %}
    {{- "" }} | {{ i.description | in_cell }}
    {{- "" }} |
  {% endfor %}
{% else %}
There are no input or output items.
{% endif %}

## Actions

| Action | Description | Goes to |
|--------|-------------|---------|
{% for a in this.actions %}
  {{- "" }}| {{ a.name }}
  {{- "" }} | {{ a.description | in_cell }}
  {{- "" }} | {% for t in a.transitions %}{% set dst = node("sdd", "user_interface_design", t.to) %}{{ dst | link(dst.name) }}{% if t.condition %} ({{ t.condition }}){% endif %}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% endfor %}
