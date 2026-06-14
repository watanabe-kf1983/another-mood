# Project Members

{% mood_view "prose.md" with (prose | selectattr("id", "equalto", "about") | first) %}

## Members

{% for member in members %}
{% mood_view "member.md" with member %}
- {{ member | link }} — {{ member.role }}
{% endfor %}

## By Role

{% for entry in by_role %}
{% mood_view "by_role.md" with entry %}
- {{ entry | link }}
{% endfor %}
