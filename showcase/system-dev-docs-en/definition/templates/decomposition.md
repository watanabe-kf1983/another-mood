{% import "business_macros.md" as m %}
{% set parent = node("processes", this.id) %}
{% set ids = this.children | map(attribute="id") | list %}
# Diagram {{ m.number(parent) }}: decomposition of {{ parent.name }}

{{ parent.name }} decomposes into {{ this.children | length }} processes: {% for c in this.children %}{{ m.display_name(c) }}{% if not loop.last %}, {% endif %}{% endfor %}.

{# Parties outside the diagram (external entities, data stores, processes of
   other diagrams) are drawn by declaring both ends of every line. Mermaid
   allows a node to be declared again, so the same party may appear any
   number of times. #}
```mermaid
flowchart LR
{% for c in this.children %}
  {{ c.id | safe }}(("{{ m.display_name(c) | safe }}"))
{% endfor %}
{% for f in node("flows") if f.source.process_id in ids or f.target.process_id in ids %}
  {{ m.end_node(f.source) | safe }} -->|"{{ f.name | safe }}"| {{ m.end_node(f.target) | safe }}
{% endfor %}
```

| ID | Flow | From | To | Higher-level flow | Description |
|----|------|------|----|-------------------|-------------|
{% for f in node("flows") if f.source.process_id in ids or f.target.process_id in ids %}
  {{- "" }}| {{ f.id }}
  {{- "" }} | {{ f.name }}
  {{- "" }} | {{ m.end_name(f.source) }}
  {{- "" }} | {{ m.end_name(f.target) }}
  {{- "" }} | {% if f.parent_id %}{{ f.parent_id }} {{ node("flows", f.parent_id).name }}{% endif %}
  {{- "" }} | {{ f.description | in_cell }}
  {{- "" }} |
{% endfor %}
