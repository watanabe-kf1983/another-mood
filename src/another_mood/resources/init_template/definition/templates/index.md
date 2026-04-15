# Project Members

## Members

{%- for member in members %}
- [{{ member.name }}](member/{{ member.id }}.md) — {{ member.role }}
{%- endfor %}

{%- for member in members -%}
{% section "member" with member %}
{%- endfor %}

## By Role

{%- for entry in by_role %}
- [{{ entry.role }}](by_role/{{ entry.id }}.md)
{%- endfor %}

{%- for entry in by_role -%}
{% section "by_role" with entry %}
{%- endfor %}
