{% import "business_macros.md" as m %}
# {{ name }} ({{ id }})

{{ summary }}

| Item | Content |
|------|---------|
| Actors
  {{- "" }} | {% for a in actors %}{{ node("srs", "introduction", "users_and_external_systems", a.id) | link }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% if business_processes %}
  {{- "" }}| Business processes
  {{- "" }} | {% for bp in business_processes %}{{ node("srs", "introduction", "business_context", bp.id) | link(m.display_name(node("processes", bp.id))) }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% endif %}
{% if precondition %}
| Precondition | {{ precondition | in_cell }} |
{% endif %}
{% if postcondition %}
| Postcondition | {{ postcondition | in_cell }} |
{% endif %}

## Main scenario

| # | {% for a in actors %}{{ node("actors", a.id).name }}{% if not loop.last %} / {% endif %}{% endfor %} | System |
|---|------|--------|
{% for step in main_scenario %}
| {{ loop.index }} | {{ step.action | in_cell }} | {{ step.response | in_cell }} |
{% endfor %}
{% set steps_with_exceptions = main_scenario | selectattr("exceptions") | list %}
{% if steps_with_exceptions %}

## Exceptions

| Step | Condition | System |
|------|-----------|--------|
  {% for step in main_scenario %}
    {% set step_no = loop.index %}
    {% for ex in step.exceptions %}
| {{ step_no }} | {{ ex.condition | in_cell }} | {{ ex.response | in_cell }} |
    {% endfor %}
  {% endfor %}
{% endif %}
{% if requirements %}

## Requirements

{{ requirements | render("requirements_table.md") }}
{% endif %}

