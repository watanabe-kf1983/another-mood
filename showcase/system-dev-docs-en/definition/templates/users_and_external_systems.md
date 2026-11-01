# Users

The human roles that operate this system directly, and the functions each role is involved in.

| User | Role | Functions |
|------|------|-----------|
{% for a in this if a.kind == "person" %}
  {{- "" }}| {{ a | anchor }}{{ a.name }}
  {{- "" }} | {{ a.description | in_cell }}
  {{- "" }} | {% for uc in a.use_cases %}{{ node("srs", "requirements", "functional", uc.id) | link(uc.name) }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% endfor %}

# External systems

The external systems this system works with, and the functions each is involved in.

| External system | Role | Functions |
|-----------------|------|-----------|
{% for a in this if a.kind == "external_system" %}
  {{- "" }}| {{ a | anchor }}{{ a.name }}
  {{- "" }} | {{ a.description | in_cell }}
  {{- "" }} | {% for uc in a.use_cases %}{{ node("srs", "requirements", "functional", uc.id) | link(uc.name) }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% endfor %}
