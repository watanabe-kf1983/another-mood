# Project Members

{{ node("prose", "about") | render("prose.md") }}

## Members

{% for member in members %}
{{- member | render("member.md") -}}
- {{ member | link }} — {{ member.role }}
{% endfor %}

## By Role

{% for entry in by_role %}
{{- entry | render("by_role.md") -}}
- {{ entry | link }}
{% endfor %}
