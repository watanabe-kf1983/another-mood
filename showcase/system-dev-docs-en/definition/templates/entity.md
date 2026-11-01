# {{ this.name }}

{{ this.description }}

| Attribute | Type | Required | PK | References | Description |
|-----------|------|----------|----|------------|-------------|
{# An x-ref can only name an entity ID, and ref.attribute is a bare string, so
   a misspelling still builds. Match it against the attributes of the
   referenced entity by name, and if absent mark the table so a reader
   notices. #}
{% for a in this.attributes %}
  {% set dst = node("sdd", "data_design", "logical_data_model", a.ref.entity_id) if a.ref else none %}
  {{- "" }}| {{ a.name }}
  {{- "" }} | {{ a.type }}
  {{- "" }} | {{ "✓" if a.required }}
  {{- "" }} | {{ "✓" if a.primary_key }}
  {{- "" }} | {% if a.ref %}{{ dst | link(dst.name) }}.{{ a.ref.attribute }}{% if a.ref.attribute not in dst.attributes | map(attribute="name") | list %} (no such attribute in the referenced entity){% endif %}{% endif %}
  {{- "" }} | {{ a.description | in_cell }}
  {{- "" }} |
{% endfor %}

{# The three lines below are reverse lookups: the records that point at this
   entity, filtered by this.id. No headings: in the book edition each entity's
   heading is already at level 6 (Markdown's limit). A line is not dropped when
   nothing matches but says (none): that an entity appears on no screen is a
   fact to show, not to hide. The data stores an entity implements have no home
   and no anchor, so their names are shown without a link. #}
Used by: {% for a in node("data_access") if a.entity_id == this.id %}{{ node("srs", "requirements", "functional", a.use_case_id) | link(a.use_case_id) }} {{ node("use_cases", a.use_case_id).name }} ({{ a.operation }}){% if not loop.last %}, {% endif %}{% else %}(none){% endfor +%}

Implements: {% for s in this.data_stores | default([]) %}{{ node("data_stores", s.id).name }}{% if not loop.last %}, {% endif %}{% else %}(none){% endfor +%}

Shown on: {% for s in node("sdd", "user_interface_design") if this.id in s.io_items | default([]) | selectattr("ref") | map(attribute="ref.entity_id") | list %}{{ s | link(s.name) }} ({{ s.id }}){% if not loop.last %}, {% endif %}{% else %}(none){% endfor +%}
