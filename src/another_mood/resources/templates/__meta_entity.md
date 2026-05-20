# Entity Definition: {{ id }}{% if builtin %} (built-in){% endif %}

[→ Entity Data](../__table_view/{{ id }}.md)

## Type Diagram

{% set ns = namespace(subtree_ids=[], fk_target_ids=[]) -%}
{% for entity in entities if entity.id == id or entity.id.startswith(id ~ ".") -%}
{%- set ns.subtree_ids = ns.subtree_ids + [entity.id] -%}
{% endfor -%}
{% for entity in entities if entity.id in ns.subtree_ids -%}
{%- for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity not in ns.subtree_ids and attr.x_ref.entity not in ns.fk_target_ids -%}
{%- set ns.fk_target_ids = ns.fk_target_ids + [attr.x_ref.entity] -%}
{%- endfor -%}
{% endfor -%}
```mermaid
classDiagram
{% for entity in entities if entity.id in ns.subtree_ids -%}
class {{ entity.item_type.id | mermaid_class_id }}["{{ entity.item_type.id }}"] {
{% for attr in entity.item_type.attributes -%}
{{ "  " }}{% if attr.required %}*{% endif %}{{ attr.id }} : {{ attr.child_item_type or attr.type }}{% if attr.x_ref %} [FK]{% endif %}
{% endfor -%}
}
{% endfor -%}
{% for entity in entities if entity.id in ns.fk_target_ids -%}
class {{ entity.item_type.id | mermaid_class_id }}["{{ entity.item_type.id }}"]
{% endfor -%}
{% set draw_ids = ns.subtree_ids + ns.fk_target_ids -%}
{% for entity in entities if entity.id in ns.subtree_ids and entity.parent_entity and entity.parent_entity in draw_ids -%}
{%- set parent = entities | selectattr('id', 'eq', entity.parent_entity) | first -%}
{{ parent.item_type.id | mermaid_class_id }} *-- {{ entity.item_type.id | mermaid_class_id }}
{% endfor -%}
{% for entity in entities if entity.id in ns.subtree_ids -%}
{%- for attr in entity.item_type.attributes if attr.x_ref -%}
{%- set target = entities | selectattr('id', 'eq', attr.x_ref.entity) | first -%}
{% if target -%}
{{ entity.item_type.id | mermaid_class_id }} --> {{ target.item_type.id | mermaid_class_id }} : {{ attr.id }}
{% endif -%}
{%- endfor -%}
{% endfor -%}
```

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
| id | type | required | references | validation | metadata |
|----|------|----------|------------|------------|----------|
{% for attribute in entity.item_type.attributes -%}
{%- set array_suffix = "[]" if attribute.child_item_type and attribute.type.endswith("[]") else "" -%}
{%- set type_cell = "`" ~ (attribute.child_item_type or attribute.type) ~ array_suffix ~ "`" -%}
| `{{ attribute.id }}` | {{ type_cell }} | {% if attribute.required %}yes{% endif %} | {% if attribute.x_ref %}[`{{ attribute.x_ref.entity }}.{{ attribute.x_ref.attribute }}`]({{ attribute.x_ref.entity }}.md){% endif %} | {% if attribute.validation %}`{{ attribute.validation | to_yaml(true) }}`{% endif %} | {% if attribute.metadata %}`{{ attribute.metadata | to_yaml(true) }}`{% endif %} |
{% endfor -%}
{%- else -%}
(no attributes defined yet)
{%- endif %}

{% endfor -%}
