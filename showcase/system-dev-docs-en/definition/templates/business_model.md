{% import "business_macros.md" as m %}
{% set whole = node("processes") | rejectattr("parent_id") | first %}
# Business model

Shows the whole of {{ whole.name }}, which this system supports, as a levelled data flow diagram (DFD). The boundary of the diagrams is {{ whole.name }}, not this system. This system takes on part of the business; its extent is given under {{ node("srs", "introduction", "business_context") | link("Business processes in scope") }}, and its boundary is drawn by the system context chapter of the design document. The context diagram, which shows the whole business as one process with its inputs and outputs, is in the {{ node("srs", "introduction", "business_context") | link("business context") }}; here the processes are decomposed step by step, and each decomposition diagram shows the flow of data between its processes and the data stores and external entities.

## Process hierarchy

| No. | Process | Description | Decomposition |
|-----|---------|-------------|---------------|
{% for p in node("processes") %}
  {% set decomposition = this | selectattr("id", "equalto", p.id) | list %}
  {{- "" }}| {% if p.parent_id %}{{ m.number(p) }}{% endif %}
  {{- "" }} | {% if p.parent_id and not decomposition %}{{ node("srs", "introduction", "business_context", p.id) | link(p.name) }}{% else %}{{ p.name }}{% endif %}
  {{- "" }} | {{ p.description | in_cell }}
  {{- "" }} | {% for d in decomposition %}{{ d | link("Diagram " ~ m.number(p)) }}{% endfor %}
  {{- "" }} |
{% endfor %}

The row without a number is the business as a whole, whose decomposition is diagram 0. Numbered processes without a decomposition diagram are the leaves, the units of business work that the scope table and the use case descriptions refer to (the name links to that row).

## Data stores

| Data store | Description |
|------------|-------------|
{% for s in node("data_stores") %}
| {{ s.name }} | {{ s.description | in_cell }} |
{% endfor %}

## External entities

| External entity | Description |
|-----------------|-------------|
{% for e in node("external_entities") %}
| {{ e.name }} | {{ e.description | in_cell }} |
{% endfor %}

External entities are the parties outside the boundary of the business; their boundary differs from that of this system's actors.

{{ node(path="/prose/srs/business_model").content | relink }}

## Decomposition diagrams

For each decomposed process, shows its child processes and the flows the children exchange with parties outside the diagram (external entities, data stores, processes of other diagrams). A line to a party outside the diagram bundles the lines drawn in the higher-level diagram as inputs and outputs of the parent process, and the flow table of each diagram records that correspondence (the higher-level flow). There are {{ this | length }} diagrams, {% for d in this %}{{ d | link("Diagram " ~ m.number(node("processes", d.id))) }}{% if not loop.last %}, {% endif %}{% endfor %}, in the same order as the process hierarchy.

{% for d in this %}
{{ d | render("decomposition.md") | under_heading("###") -}}
{% endfor %}

## Balancing check

The inputs and outputs of a decomposition diagram must match the flows drawn in the higher-level diagram as inputs and outputs of the parent process (balancing). For each decomposition diagram, the check confirms that every flow crossing the boundary has a higher-level flow whose ends correspond, that no flow staying inside the diagram has a higher-level flow, and that every input and output of the parent process is bundled by some flow in the diagram. Data stores lie inside the business and do not appear in the context diagram, so a flow to or from a data store needs a higher-level flow only when that data store is drawn in the higher-level diagram. The check also confirms that the source and the target of every flow each resolve to exactly one party.

{# The rules of the check are as stated in the text above. In addition: whether
   a flow is "inside the diagram" is decided by the same rule as the drawing
   (is the process at its end a child process), and flows between processes
   across levels are, as in the drawing, not expected. A data store "drawn in
   the higher-level diagram" means one with a flow to or from a sibling of the
   parent process. That source / target resolve to exactly one party is also
   checked here: "exactly one" of a three-way object cannot be said in the
   schema. Mismatching rows accumulate in this {% set %} block. Inside the
   block the default escaping applies, and the | safe on output avoids doubling
   it. #}
{% set mismatches %}
  {% for f in node("flows") %}
    {% for x in [f.source, f.target] %}
      {% if (1 if x.process_id else 0) + (1 if x.data_store_id else 0) + (1 if x.external_entity_id else 0) != 1 %}
        {{- "" }}| | {{ f.id }} {{ f.name }} | the {{ "source" if loop.index == 1 else "target" }} does not resolve to exactly one party |
      {% endif %}
    {% endfor %}
  {% endfor %}
  {% for d in this %}
    {% set diagram = d | link("Diagram " ~ m.number(node("processes", d.id))) %}
    {% set ids = d.children | map(attribute="id") | list %}
    {% set grandparent = node("processes", d.id).parent_id or "" %}
    {% for g in node("flows") if g.source.process_id == d.id %}
      {% for f in node("flows") if f.parent_id == g.id and f.source.process_id in ids %}{% else %}
        {{- "" }}| {{ diagram }} | {{ g.id }} {{ g.name }} | an output of the parent process, but bundled by no flow in the diagram |
      {% endfor %}
    {% endfor %}
    {% for g in node("flows") if g.target.process_id == d.id %}
      {% for f in node("flows") if f.parent_id == g.id and f.target.process_id in ids %}{% else %}
        {{- "" }}| {{ diagram }} | {{ g.id }} {{ g.name }} | an input of the parent process, but bundled by no flow in the diagram |
      {% endfor %}
    {% endfor %}
    {% for f in node("flows") if f.source.process_id in ids or f.target.process_id in ids %}
      {% set source_inside = f.source.process_id in ids %}
      {% set target_inside = f.target.process_id in ids %}
      {% if source_inside and target_inside %}
        {% if f.parent_id %}
          {{- "" }}| {{ diagram }} | {{ f.id }} {{ f.name }} | stays inside the diagram, yet has the higher-level flow {{ f.parent_id }} |
        {% endif %}
      {% elif not f.parent_id %}
        {% set S = f.target.data_store_id if source_inside else f.source.data_store_id %}
        {% if S %}
          {% for g in node("flows") if (g.source.data_store_id == S or g.target.data_store_id == S) and ((g.source.process_id and (node("processes", g.source.process_id).parent_id or "") == grandparent) or (g.target.process_id and (node("processes", g.target.process_id).parent_id or "") == grandparent)) %}
            {% if loop.first %}
              {{- "" }}| {{ diagram }} | {{ f.id }} {{ f.name }} | {{ node("data_stores", S).name }} is drawn in the higher-level diagram, yet there is no higher-level flow |
            {% endif %}
          {% endfor %}
        {% else %}
          {{- "" }}| {{ diagram }} | {{ f.id }} {{ f.name }} | crosses the boundary of the diagram, yet has no higher-level flow |
        {% endif %}
      {% else %}
        {% set g = node("flows", f.parent_id) %}
        {% set corresponds = (m.end_key(g.source) == "process:" ~ d.id and m.end_key(g.target) in [m.end_key(f.target), m.parent_end_key(f.target)]) if source_inside else (m.end_key(g.target) == "process:" ~ d.id and m.end_key(g.source) in [m.end_key(f.source), m.parent_end_key(f.source)]) %}
        {% if not corresponds %}
          {{- "" }}| {{ diagram }} | {{ f.id }} {{ f.name }} | the ends do not correspond to those of the higher-level flow {{ g.id }} {{ g.name }} ({{ m.end_name(g.source) }} → {{ m.end_name(g.target) }}) |
        {% endif %}
      {% endif %}
    {% endfor %}
  {% endfor %}
{% endset %}
{% if mismatches | trim %}
| Diagram | Flow | Mismatch |
|---------|------|----------|
{{ mismatches | trim | safe }}
{% else %}
In all {{ this | length }} decomposition diagrams the inputs and outputs match between the levels, and every flow's source and target resolve to one party.
{% endif %}
