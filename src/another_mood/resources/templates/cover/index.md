# Another Mood

## User Reports

{% for e in editions if not e.is_system %}
- [{{ e.name }}]({{ e.dir_segment | safe }}/)
{% endfor %}

## Database Information

{% for e in editions if e.is_system %}
Schema, data, and query diagnostics for this database — [browse]({{ e.dir_segment | safe }}/).
{% endfor %}
