{% set entities = node(path="/__definition/entities") %}
# Data: {{ id }}

{% if (entities | child(id)).view %}
[← View Definition]({{ node("__view_defs", id) | href }})
{% else %}
[← Entity Definition]({{ node("__entity_defs", id) | href }})
{% endif %}

{% filter under_heading("#") %}
    {% for entity in entities if entity.id == id or entity.id is startingwith(id ~ ".") %}
        {{- entity.id | render("record_table.md") -}}
    {% endfor %}
{% endfilter %}
