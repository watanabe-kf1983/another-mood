# {{ role }}

{% for member in members %}
- [{{ member.name }}](../member/{{ member.id }}.md)
{%- endfor %}
