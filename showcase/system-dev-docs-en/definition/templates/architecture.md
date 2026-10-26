# System architecture

Shows the components the software of this system is made of and their dependencies, the use cases, entities and design decisions each component takes on, and the deployment.

## Component diagram

{# Arrows are dependencies (the direction of calls). The mapping to entities is
   not drawn; the table below carries it. Drawn, an entity handled by several
   components, such as book, would cross lines and obscure the layers of
   dependency. #}
{% filter dedent %}
  ```mermaid
  flowchart BT
  subgraph app["{{ node(path="/system").name | safe }}"]
  {% for c in components %}
    {{ c.id | safe }}["{{ c.name | safe }}"]
  {% endfor %}
  end
  {% for c in components %}
    {% for d in c.dependencies | default([]) %}
      {{ c.id | safe }} --> {{ d.id | safe }}
    {% endfor %}
  {% endfor %}
  ```
{% endfilter %}

An arrow points in the direction of the call. A component with no outgoing arrow is a foundation that calls no other component.

{{ node(path="/prose/sdd/component_diagram").content | relink }}

## Components

| ID | Component | Responsibility | Use cases | Entities | Design decisions |
|----|-----------|----------------|-----------|----------|------------------|
{% for c in components %}
  {{- "" }}| {{ c | anchor }}{{ c.id }}
  {{- "" }} | {{ c.name }}
  {{- "" }} | {{ c.responsibility | in_cell }}
  {{- "" }} | {% for u in c.use_cases | default([]) %}{{ node("srs", "requirements", "functional", u.id) | link(u.id) }} {{ node("use_cases", u.id).name }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} | {% for e in c.entities | default([]) %}{{ node("sdd", "data_design", "logical_data_model", e.id) | link }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} | {% for d in c.design_decisions | default([]) %}{{ node("sdd", "introduction", "design_decisions", d.id) | link(d.id) }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% endfor %}

The use cases column lists the use cases the component realises, the entities column the entities it reads and writes itself, and the design decisions column the {{ node("sdd", "introduction", "design_decisions") | link("design decisions") }} it takes on. Reads and writes done by calling another component are not listed in the caller's entities column, so the column is narrower than the rows of the {{ node("sdd", "data_design", "crud_matrix") | link("CRUD matrix") }} bundled per component. Decisions that apply to the whole system are placed on no component.

{{ prose | child("sdd/architecture") | render("prose.md") | under_heading("#") }}
