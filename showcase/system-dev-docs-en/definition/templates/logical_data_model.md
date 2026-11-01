# Logical data model

Shows the data this system handles as a logical-level model: an ER diagram, the entity list and the entity definitions.

## ER diagram

{# The ER diagram draws the relations, so it shows primary and foreign keys
   only. The full attributes belong to the entity definition tables below;
   putting them in the diagram too would show the same information twice on
   one page. Cardinalities are derived from the data alone: on the referenced
   side, exactly one (||) when the attribute is required, zero or one (|o)
   otherwise. The referencing side is always zero or more (}o): whether every
   referenced record has at least one referencing record is not in the data,
   so no assumption is made. #}
{% filter dedent %}
  ```mermaid
  erDiagram
  {% for e in this %}
    "{{ e.name | safe }}" {
    {% for a in e.attributes if a.primary_key or a.ref %}
      {{ a.type | safe }} {{ a.name | safe }} {{ ("PK, FK" if a.primary_key and a.ref else ("PK" if a.primary_key else "FK")) | safe }}
    {% endfor %}
    }
  {% endfor %}
  {% for e in this %}
    {% for a in e.attributes if a.ref %}
      "{{ e.name | safe }}" }o--{{ ("||" if a.required else "|o") | safe }} "{{ node("sdd", "data_design", "logical_data_model", a.ref.entity_id).name | safe }}" : "{{ a.name | safe }}"
    {% endfor %}
  {% endfor %}
  ```
{% endfilter %}

## Entities

| Entity | Kind | Term | Implements | Description |
|--------|------|------|------------|-------------|
{% for e in this %}
  {{- "" }}| {{ e | link(e.name) }}
  {{- "" }} | {{ e.kind | capitalize }}
  {{- "" }} | {% if e.term_id %}{{ node("srs", "glossary", e.term_id) | link }}{% endif %}
  {{- "" }} | {% for s in e.data_stores | default([]) %}{{ node("data_stores", s.id).name }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} | {{ e.description | in_cell }}
  {{- "" }} |
{% endfor %}

A resource is a thing that persists as a subject of the business; an event is a record of something happening in the business. Resources come first, then events in order of creation. The Implements column names the data stores of the {{ node("srs", "appendices", "business_model") | link("business model") }} in the requirements specification that the entity implements: one ledger may be implemented by a parent and a line entity, and one entity may serve as two ledgers.

{{ node(path="/prose/sdd/logical_data_model").content | relink }}

## Entity definitions

For each entity, its attributes and the use cases and screens that use it. There are {{ this | length }} entities, {% for e in this %}{{ e | link(e.name) }}{% if not loop.last %}, {% endif %}{% endfor %}, in the same order as the entity list.

{% for e in this %}
{{ e | render("entity.md") | under_heading("###") -}}
{% endfor %}
