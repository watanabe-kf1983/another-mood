{#- A macro's return value is escaped again by the caller's {{ }}, so every
    substitution inside the macros is emitted raw with | safe (escaping inside
    as well would double it). The caller adds | safe where it belongs: not in a
    table cell, but inside Mermaid. -#}
{# number derives the DFD convention (the children of diagram 0 are 1, 2, ...,
   their children 1.1, 1.2, ...) from the parent-child relation and the order of
   description of the processes. It is not held in the data. The business as a
   whole (the process without a parent) is 0. #}
{% macro number(p) -%}
  {% if p.parent_id %}
{% set prefix %}{{ number(node("processes", p.parent_id)) | safe }}{% endset %}
{% for s in node("processes") if s.parent_id == p.parent_id %}{% if s.id == p.id %}{% if prefix == "0" %}{{ loop.index | safe }}{% else %}{{ prefix | safe }}.{{ loop.index | safe }}{% endif %}{% endif %}{% endfor %}
{% else %}0{% endif %}
{%- endmacro %}
{% macro display_name(p) -%}
{% if p.parent_id %}{{ number(p) | safe }} {{ p.name | safe }}{% else %}{{ p.name | safe }}{% endif %}
{%- endmacro %}
{% macro end_name(x) -%}
{% if x.process_id %}{{ display_name(node("processes", x.process_id)) | safe }}{% elif x.data_store_id %}{{ node("data_stores", x.data_store_id).name | safe }}{% else %}{{ node("external_entities", x.external_entity_id).name | safe }}{% endif %}
{%- endmacro %}
{% macro end_node(x) -%}
{% if x.process_id %}{{ x.process_id | safe }}(("{{ display_name(node("processes", x.process_id)) | safe }}")){% elif x.data_store_id %}{{ x.data_store_id | safe }}[("{{ node("data_stores", x.data_store_id).name | safe }}")]{% else %}{{ x.external_entity_id | safe }}["{{ node("external_entities", x.external_entity_id).name | safe }}"]{% endif %}
{%- endmacro %}
{# end_key / parent_end_key serve the comparison of the balancing check. They
   fold a flow end (the three-way source / target object) into one string
   "kind:ID", and parent_end_key further replaces an end that is a process with
   a parent by that parent. This lets the check confirm by string comparison
   that the end of a lower-level flow corresponds to the end of the
   higher-level flow (the same, or one level up). #}
{% macro end_key(x) -%}
{% if x.process_id %}process:{{ x.process_id | safe }}{% elif x.data_store_id %}data_store:{{ x.data_store_id | safe }}{% else %}external_entity:{{ x.external_entity_id | safe }}{% endif %}
{%- endmacro %}
{% macro parent_end_key(x) -%}
{% if x.process_id and node("processes", x.process_id).parent_id %}process:{{ node("processes", x.process_id).parent_id | safe }}{% else %}{{ end_key(x) | safe }}{% endif %}
{%- endmacro %}
