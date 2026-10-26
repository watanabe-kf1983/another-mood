| ID | Requirement | Rationale | Priority |
|----|-------------|-----------|----------|
{% for r in this %}
| {{ r | anchor }}{{ r.id }} | **{{ r.title }}**<br>{{ r.statement | in_cell }} | {{ r.rationale | in_cell }} | {{ r.priority | capitalize }} |
{% endfor %}
