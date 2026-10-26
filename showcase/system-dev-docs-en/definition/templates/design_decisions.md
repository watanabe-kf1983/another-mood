# Design decisions

Lists the design decisions of this system, each with its rationale and the requirements it is based on.

{% for d in this %}
{{ d | anchor }}
## {{ d.id }} {{ d.title }}

{{ d.decision }}

### Rationale

{{ d.rationale }}
  {% if d.basis_requirements %}

### Basis requirements

    {# basis_requirements hold only IDs, so the title is looked up with
       node("requirements", id), but the link is made to the requirement's home
       (the copy in chapter 3 of the SRS: under the use case description row
       for a functional requirement, under the kind row otherwise). The node
       of the requirements entity itself is rendered nowhere, so | link on it
       would not land. #}
    {% for b in d.basis_requirements %}
      {% set r = node("requirements", b.id) %}
      {% if r.use_case_id %}
        {% set home = node("srs", "requirements", "functional", r.use_case_id, "requirements", r.id) %}
      {% else %}
        {% set home = node("srs", "requirements", "non_functional", r.kind, "requirements", r.id) %}
      {% endif %}
- {{ home | link(r.id) }} {{ r.title }}
    {% endfor %}
  {% endif %}

{% endfor %}
