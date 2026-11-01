{#- The heading and the lead sentence of each non-functional requirement kind,
    keyed by the kind enum value. Imported by the requirements and verification
    chapters, which both name the kinds. -#}
{% set heading = {
  "external_interface": "External interface requirements",
  "quality": "Quality requirements",
  "design_constraint": "Design constraints"
} %}
{% set lead = {
  "external_interface": "The requirements on the interfaces between this system and its users and external systems.",
  "quality": "The requirements on how the functions are delivered: performance, concurrent use, preservation of records and the like.",
  "design_constraint": "The requirements that limit the design choices."
} %}
