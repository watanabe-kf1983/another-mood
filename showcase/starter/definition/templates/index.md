# Project Members

{% render "prose.md" with node("prose", "about") %}

## Members

{% for member in members %}
{% render "member.md" with member %}
- {{ member | link }} — {{ member.role }}
{% endfor %}

## By Role

{% for entry in by_role %}
{% render "by_role.md" with entry %}
- {{ entry | link }}
{% endfor %}
