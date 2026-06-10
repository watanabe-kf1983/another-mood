# Project Members

{% mood_view "prose.md" with (prose | selectattr("id", "equalto", "about") | first) inline %}

## Members

{%- for member in members %}
- {{ member | link }} — {{ member.role }}
{%- endfor %}

{%- for member in members -%}
{% mood_view "member.md" with member %}
{%- endfor %}

## By Role

{%- for entry in by_role %}
- {{ entry | link }}
{%- endfor %}

{%- for entry in by_role -%}
{% mood_view "by_role.md" with entry %}
{%- endfor %}
