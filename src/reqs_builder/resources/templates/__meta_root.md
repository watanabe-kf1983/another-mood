# Meta Documentation

## Entities

{% if __definition is defined and __definition.entities -%}
{% for entity in __definition.entities | sort(attribute='builtin') -%}
- [{{ entity.id }}](__meta_entity/{{ entity.id }}.md){% if entity.builtin %} (built-in){% endif %}{% if entity.metadata and entity.metadata.title %} — {{ entity.metadata.title }}{% endif %}
{% endfor %}
{% for entity in __definition.entities -%}
{% section "__meta_entity" with entity %}
{%- endfor %}
{%- else -%}
（エンティティはまだ定義されていません）
{%- endif %}

## References

{% if __definition is defined and __definition.references -%}
| From | To |
|------|-----|
{% for ref in __definition.references -%}
| {{ ref.from }} | {{ ref.to }} |
{% endfor -%}
{%- else -%}
（参照はまだ定義されていません）
{%- endif %}
