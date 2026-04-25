# Definition: {{ id }}{% if builtin %} (built-in){% endif %}

{% if parent_entity -%}
**parent:** [`{{ parent_entity }}`](../__meta_entity/{{ parent_entity }}.md)

---

{% endif -%}
[→ Data](../__table_view/{{ id }}.md)

## Item Type: {{ item_type.id }}

{% if item_type.metadata -%}
### metadata

```yaml
{{ item_type.metadata | to_yaml }}
```

{% endif -%}
### attributes

{% if item_type.attributes -%}
| id | type | required | metadata | validation |
|----|------|----------|----------|------------|
{% for attribute in item_type.attributes -%}
{%- set type_cell = "[`" ~ attribute.entity ~ "`](../__meta_entity/" ~ attribute.entity ~ ".md)" if attribute.entity else "`" ~ attribute.type ~ "`" -%}
| `{{ attribute.id }}` | {{ type_cell }} | {% if attribute.required %}yes{% endif %} | {% if attribute.metadata %}`{{ attribute.metadata | to_yaml(true) }}`{% endif %} | {% if attribute.validation %}`{{ attribute.validation | to_yaml(true) }}`{% endif %} |
{% endfor -%}
{%- else -%}
(no attributes defined yet)
{%- endif %}
