{% set entities = node("/__definition/entities") %}
# Entity Data: {{ id }}

[← Entity Definition]({{ node("__entity_defs", id) | href }})

{% filter under_heading("#") %}
    {% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") %}
        {% mood_view "record_table.md" with entity %}

    {% endfor %}
{% endfilter %}
