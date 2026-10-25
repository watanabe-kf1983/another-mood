{% set entities = node(path="/__definition/entities") %}
# Data: {{ id }}

[← Entity Definition]({{ node("__defs", "entities", id) | href }})

{% filter under_heading("#") %}
    {% for entity in entities if entity.id == id or entity.id is startingwith(id ~ ".") %}
        {{- entity.id | render("record_table.md") -}}
    {% endfor %}
{% endfilter %}
