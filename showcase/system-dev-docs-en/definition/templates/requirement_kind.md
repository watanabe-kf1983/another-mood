{% import "requirement_kinds.md" as k %}
# {{ k.heading[id] }}

{{ k.lead[id] }}

{{ requirements | render("requirements_table.md") }}
