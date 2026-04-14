# {{ id }}

**From:** {{ from }}
{% if grouped %}
**Grouped by:** {{ grouped.by }}{% if grouped.as %} (as {{ grouped.as }}){% endif %}
{% endif %}
## Select

{% if select -%}
| Item | As |
|------|----|
{% for entry in select -%}
| {{ entry.item }} | {{ entry.as or entry.item }} |
{% endfor -%}
{%- else -%}
(no select items defined)
{%- endif %}
