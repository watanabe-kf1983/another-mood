# {{ role }}

{% for member in members %}
- [{{ member.name }}](../member/{{ member.id | as_url }}.md)
{%- endfor %}
