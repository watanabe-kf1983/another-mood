# {{ name }}

{{ description }}

| フィールド | 型 | 備考 |
|-----------|-----|------|
{% for field in fields -%}
| {{ field.name }} | {{ field.type }} | {% if field.pk %}PK{% endif %}{% if field.fk %}FK → {{ field.fk }}{% endif %} |
{% endfor %}
