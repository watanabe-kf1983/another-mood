{#- The subjects functional / non_functional are copies of the chapter 3 views,
    and this chapter only redraws the same rows with the verification method /
    fit criterion columns. So the rows are not rendered but iterated with for,
    and the table is drawn with include: rendering them would make the chapter
    4 rows the home and give the web edition a second set of per-use-case
    pages. -#}
{% import "requirement_kinds.md" as k %}
# Verification

Shows the verification method and fit criterion of each requirement of the {{ node("srs", "requirements") | link("Requirements") }} chapter, functional requirements per use case and non-functional requirements per kind, in the same order as the requirements.

## Verification of functional requirements

{% for uc in functional %}
### {{ node("srs", "requirements", "functional", uc.id) | link(uc.name) }} ({{ uc.id }})

  {% set requirements = uc.requirements %}
  {% include "verification_table.md" %}

{% endfor %}
## Verification of non-functional requirements

{% for kind in non_functional %}
### {{ node("srs", "requirements", "non_functional", kind.id) | link(k.heading[kind.id]) }}

  {% set requirements = kind.requirements %}
  {% include "verification_table.md" %}

{% endfor %}
