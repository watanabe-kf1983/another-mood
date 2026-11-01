# Product functions

Lists the main functions this system provides, in the order of the business flow.

| ID | Function | Summary | Actors |
|----|----------|---------|--------|
{% for uc in this %}
  {{- "" }}| {{ node("srs", "requirements", "functional", uc.id) | link(uc.id) }}
  {{- "" }} | {{ uc.name }}
  {{- "" }} | {{ uc.summary | in_cell }}
  {{- "" }} | {% for a in uc.actors %}{{ node("srs", "introduction", "users_and_external_systems", a.id) | link }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} |
{% endfor %}
