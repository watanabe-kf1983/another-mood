# {{ name }} {{ version }}

{{ description }}

- **License**: {% for lic in licenses %}{{ lic.license.id or lic.license.name or lic.expression }}{% if not loop.last %}, {% endif %}{% endfor %}

- **Dependency**: {% if required_by_root %}direct{% else %}transitive{% endif %}

- **Package URL**: {{ code_inline(purl) }}

{# Node ids are positional so package names never need escaping for
   Mermaid; the names go in the quoted labels. #}
```mermaid
flowchart LR
  self["{{ name | safe }}"]
{% if required_by_root %}
  root["{{ node("root_component") | label | safe }}"] --> self
{% endif %}
{% for edge in used_by %}
  u{{ loop.index }}["{{ edge.source.name | safe }}"] --> self
{% endfor %}
{% for edge in depends_on %}
  self --> d{{ loop.index }}["{{ edge.target.name | safe }}"]
{% endfor %}
  style self stroke-width:3px
```

## Depends on

{% if depends_on %}
{% for edge in depends_on %}
- {{ node("component", edge.target.name) | link }} {{ edge.target.version }}
{% endfor %}
{% else %}
_No dependencies._
{% endif %}

## Used by

{% if required_by_root %}
- {{ node("root_component") | label }} (the root component)
{% endif %}
{% for edge in used_by %}
- {{ node("component", edge.source.name) | link }} {{ edge.source.version }}
{% endfor %}

{% if externalReferences %}
## Links

{% for ref in externalReferences %}
- [{{ ref.url }}]({{ ref.url | as_url }}) ({{ ref.type }})
{% endfor %}
{% endif %}
