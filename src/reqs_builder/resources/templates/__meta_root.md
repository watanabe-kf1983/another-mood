# Meta Documentation

## Entities

{% if __definition.entities -%}
{% for entity in __definition.entities | sort(attribute='builtin') -%}
- [{{ entity.id }}](__meta_entity/{{ entity.id }}.md){% if entity.builtin %} (built-in){% endif %}{% if entity.metadata.title %} — {{ entity.metadata.title }}{% endif %}
{% endfor %}
{% for entity in __definition.entities -%}
{% section "__meta_entity" with entity %}
{%- endfor %}
{%- else -%}
(no entities defined yet)
{%- endif %}

## References

{% if __definition.references -%}
| From | To |
|------|-----|
{% for ref in __definition.references -%}
| {{ ref.from }} | {{ ref.to }} |
{% endfor -%}
{%- else -%}
(no references defined yet)
{%- endif %}
