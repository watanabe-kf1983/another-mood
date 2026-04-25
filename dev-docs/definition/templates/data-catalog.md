# データカタログ出力形状

SchemaInspector が `inspect_schemas_dir` に出力するデータカタログの形状。
入力例: showcase/examples/ecommerce の entities / relations スキーマ。

## 属性一覧

{% for entity in entities %}
### {{ entity.id }}

| Id | Type | Required |
|----|------|----------|
{% for attribute in entity.attributes -%}
| {{ attribute.id }} | {{ attribute.type }} | {{ "yes" if attribute.required else "no" }} |
{% endfor %}
{% endfor %}

## クラス図

```mermaid
classDiagram
{%- for entity in entities %}
    class {{ entity.id }} {
        <<entity>>
{%- for attribute in entity.attributes %}
        {{ attribute.type }} {{ attribute.id }}{% if attribute.required %}*{% endif %}
{%- endfor %}
    }
{%- endfor %}
{%- for ref in references %}
    {{ ref.to }} <-- "{{ ref.from }}" {{ ref.from.split(".")[0] }}
{%- endfor %}
```

## ERD

```mermaid
erDiagram
{%- for entity in entities %}
    {{ entity.id }} {
{%- for attribute in entity.attributes %}
        {{ attribute.type }} {{ attribute.id | replace(".", "_") }}
{%- endfor %}
    }
{%- endfor %}
{%- for ref in references %}
    {{ ref.to }} ||--o{ {{ ref.from.split(".")[0] }} : "{{ ref.from }}"
{%- endfor %}
```

## references

| From | To |
|------|----|
{% for ref in references -%}
| {{ ref.from }} | {{ ref.to }} |
{% endfor %}
