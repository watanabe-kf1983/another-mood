{% set entities = node(path="/__definition/entities") %}
# Entity Data: {{ id }}

[← Entity Definition]({{ node("__entity_defs", id) | href }})

{% filter under_heading("#") %}
    {% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") %}
        {% render "record_table.md" with entity.id %}

    {% endfor %}
{% endfilter %}
