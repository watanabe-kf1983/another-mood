# {{ category }} の ER図

## エンティティ一覧

{% for entity in entities %}
### {{ entity.name }}

{{ entity.description }}

| フィールド | 型 | 備考 |
|-----------|-----|------|
{% for field in entity.fields -%}
| {{ field.name }} | {{ field.type }} | {% if field.pk %}PK{% endif %}{% if field.fk %}FK → {{ field.fk }}{% endif %} |
{% endfor %}

{% endfor %}
