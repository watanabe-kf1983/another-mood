# データカタログ出力形状

SchemaInspector が `inspect_schema_dir` に出力するデータカタログの形状。
入力例: example-project の entities / relations スキーマ。

## フィールド一覧

{% for entity in entities %}
### {{ entity.id }}

| Id | Type | Required |
|----|------|----------|
{% for field in entity.fields -%}
| {{ field.id }} | {{ field.type }} | {{ "yes" if field.required else "no" }} |
{% endfor %}
{% endfor %}

## クラス図

```mermaid
classDiagram
{%- for entity in entities %}
    class {{ entity.id }} {
        <<entity>>
{%- for field in entity.fields %}
        {{ field.type }} {{ field.id }}{% if field.required %}*{% endif %}
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
{%- for field in entity.fields %}
        {{ field.type }} {{ field.id | replace(".", "_") }}
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
