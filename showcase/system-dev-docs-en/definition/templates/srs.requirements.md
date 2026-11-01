# Requirements

States the requirements on this system: the functional requirements per use case, and the non-functional requirements (external interface, quality, design constraints) per kind.

## Functional requirements

For each use case, its description (actors, pre- and postconditions, main scenario and exceptions) and the requirements that belong to it. Use cases are in the order of the business flow, as in {{ node("srs", "introduction", "product_functions") | link("Product functions") }}.

{% for uc in functional %}
- {{ uc | link(uc.name) }} ({{ uc.id }})
{% endfor %}

{% for uc in functional %}
{{ uc | render("use_case.md") | under_heading("##") -}}
{% endfor %}

## Non-functional requirements

The requirements that belong to no use case, per kind (external interface / quality / design constraints).

{% import "requirement_kinds.md" as k %}
{% for kind in non_functional %}
- {{ kind | link(k.heading[kind.id]) }}
{% endfor %}

{% for kind in non_functional %}
{{ kind | render("requirement_kind.md") | under_heading("##") -}}
{% endfor %}
