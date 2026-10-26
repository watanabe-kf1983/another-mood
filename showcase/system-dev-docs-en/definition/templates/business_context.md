{% import "business_macros.md" as m %}
{% set whole = this | rejectattr("parent_id") | first %}
# Business context

Shows the flow of data between {{ whole.name }}, which this system supports, and the parties outside the business (the external entities). The boundary of the diagram is {{ whole.name }}, not this system. The decomposition of the inside of the business is shown in the {{ node("srs", "appendices", "business_model") | link("business model") }}.

{% filter dedent %}
  ```mermaid
  flowchart LR
  {% for r in this if not r.parent_id %}
    {{ r.id | safe }}(("{{ r.name | safe }}"))
    {% for f in node("flows") if f.source.process_id == r.id or f.target.process_id == r.id %}
      {{ m.end_node(f.source) | safe }} -->|"{{ f.name | safe }}"| {{ m.end_node(f.target) | safe }}
    {% endfor %}
  {% endfor %}
  ```
{% endfilter %}

# Business processes in scope

For each unit of business work (a leaf process of the business model), shows the function of this system (the use case) that supports it. A unit with no function is outside the scope of this system and stays manual.

| No. | Business process | Description | Function |
|-----|------------------|-------------|----------|
{# Rows are the leaf processes (those no process names as parent_id). The
   condition cannot be written in a view's where, so the template filters. #}
{% for p in this if p.parent_id and not (this | selectattr("parent_id", "equalto", p.id) | list) %}
  {{- "" }}| {{ p | anchor }}{{ m.number(p) }}
  {{- "" }} | {{ p.name }}
  {{- "" }} | {{ p.description | in_cell }}
  {{- "" }} | {% for uc in node("use_cases") if p.id in uc.business_processes | default([]) | map(attribute="id") | list %}{{ node("srs", "requirements", "functional", uc.id) | link(uc.name) }}{% if not loop.last %}, {% endif %}{% else %}(manual){% endfor %}
  {{- "" }} |
{% endfor %}
