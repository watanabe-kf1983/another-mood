{#- Used with include, not render (the caller sets `requirements`), so the
    subject is the variable requirements, not this. -#}
| ID | Requirement | Verification method | Fit criterion |
|----|-------------|---------------------|---------------|
{% for r in requirements %}
  {% set home = node("srs", "requirements", "functional", r.use_case_id, "requirements", r.id) if r.use_case_id else node("srs", "requirements", "non_functional", r.kind, "requirements", r.id) %}
| {{ home | link(r.id) }} | {{ r.title }} | {{ r.verification_method | capitalize }} | {{ r.fit_criterion | in_cell }} |
{% endfor %}
