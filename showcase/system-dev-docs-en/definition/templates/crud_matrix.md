{% set entities = node("sdd", "data_design", "logical_data_model") %}
# CRUD matrix

Shows which use case reads and writes which entity. Rows are the use cases (in the chronology of the business), columns the entities (in the same order as the entity list).

| Use case | {% for e in entities %}{{ e | link(e.name) }} | {% endfor +%}
|----------|{% for e in entities %}---|{% endfor +%}
{# data_access holds at most one record per (use case, entity) pair, so the
   inner for of a cell emits at most one operation. #}
{% for uc in this %}
  {{- "" }}| {{ node("srs", "requirements", "functional", uc.id) | link(uc.id) }} {{ uc.name }}
  {{- "" }} | {% for e in entities %}{% for a in uc.accesses if a.entity_id == e.id %}{{ a.operation }}{% endfor %} | {% endfor +%}
{% endfor %}
{# The summary sentence under the table. It puts the way an IPA CRUD diagram is
   used (spotting entities no use case creates or updates) into words, so the
   table need not be scanned by eye. Templates have no way to append to a
   list, so the names of the entities concerned accumulate in a namespace as a
   comma-joined string. #}
{% set ns = namespace(never_created="", never_updated="", deleted="") %}
{% for e in entities %}
  {% set flags = namespace(c=false, u=false, d=false) %}
  {% for uc in this %}
    {% for a in uc.accesses if a.entity_id == e.id %}
      {% if "C" in a.operation %}{% set flags.c = true %}{% endif %}
      {% if "U" in a.operation %}{% set flags.u = true %}{% endif %}
      {% if "D" in a.operation %}{% set flags.d = true %}{% endif %}
    {% endfor %}
  {% endfor %}
  {% if not flags.c %}{% set ns.never_created = ns.never_created ~ (", " if ns.never_created) ~ e.name %}{% endif %}
  {% if not flags.u %}{% set ns.never_updated = ns.never_updated ~ (", " if ns.never_updated) ~ e.name %}{% endif %}
  {% if flags.d %}{% set ns.deleted = ns.deleted ~ (", " if ns.deleted) ~ e.name %}{% endif %}
{% endfor %}

{% if ns.never_created %}No use case creates {{ ns.never_created }}.{% else %}Every entity is created by some use case.{% endif %} Never updated after creation: {{ ns.never_updated }}. {% if ns.deleted %}Deleted: {{ ns.deleted }}.{% else %}No entity is deleted.{% endif +%}

{{ node(path="/prose/sdd/crud_matrix").content | relink }}
