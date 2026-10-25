{% set entities = node(path="/__definition/entities") %}
# Data: {{ id }}

[← View Definition]({{ node("__defs", "views", id) | href }})

{% filter under_heading("#") %}
  {% for entity in entities if entity.id == id or entity.id is startingwith(id ~ ".") %}
    {{- entity.id | render("record_table.md") -}}
  {% endfor %}
{% endfilter %}
