# {{ role }}

{% for member in members %}
- [{{ member.name }}](../members/{{ member.id | as_url }}.md)
{%- endfor %}
