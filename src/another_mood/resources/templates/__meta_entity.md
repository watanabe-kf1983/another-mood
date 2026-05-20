# Entity Definition: {{ id }}{% if builtin %} (built-in){% endif %}

[→ Entity Data](../__table_view/{{ id }}.md)

{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") -%}
## Type: {{ entity.item_type.id }}

{% if entity.item_type.metadata -%}
### metadata

```yaml
{{ entity.item_type.metadata | to_yaml }}
```

{% endif -%}
### attributes

{% if entity.item_type.attributes -%}
| id | type | required | metadata | validation |
|----|------|----------|----------|------------|
{% for attribute in entity.item_type.attributes -%}
{%- set array_suffix = "[]" if attribute.child_item_type and attribute.type.endswith("[]") else "" -%}
{%- set type_cell = "`" ~ (attribute.child_item_type or attribute.type) ~ array_suffix ~ "`" -%}
| `{{ attribute.id }}` | {{ type_cell }} | {% if attribute.required %}yes{% endif %} | {% if attribute.metadata %}`{{ attribute.metadata | to_yaml(true) }}`{% endif %} | {% if attribute.validation %}`{{ attribute.validation | to_yaml(true) }}`{% endif %} |
{% endfor -%}
{%- else -%}
(no attributes defined yet)
{%- endif %}

{% endfor -%}
