# {{ project_name }}

## Reports

{% for e in editions if not e.is_system %}
- [{{ e.name }}]({{ e.dir_url | safe }}/)
{% endfor %}

## Database Information

{% for e in editions if e.is_system %}
Schema, views, and data as the tool read them — [browse]({{ e.dir_url | safe }}/).
{% endfor %}
