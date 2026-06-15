{% set entities = node("/__definition/entities") %}
# Entity Data: {{ id }}

[← Entity Definition]({{ node("__meta_entity", id) | href }})

{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") %}
## {{ entity.id }}

{% mood_view "_table.md" with entity %}

{% endfor %}
