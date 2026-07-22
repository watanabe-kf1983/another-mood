# 蔵書管理システム — テーブル設計書

本設計書は、小規模書店の蔵書管理システムを題材とした Another Mood のサンプルプロジェクトです。テーブル定義データから、テーブル一覧・各テーブル詳細・ER 図を自動生成しています。

## テーブル一覧

| ID | 名前 | 説明 |
|----|------|------|
{% for t in テーブル %}
{% render "テーブル詳細.md" with t %}
| {{ code_inline(t.id) }} | {{ t | link(t.名前) }} | {{ t.説明 }} |
{% endfor %}

## ドメインモデル図 (Mermaid classDiagram)

ドメイン層から見たクラス図。`列_with_ドメイン型` クエリで `列.型` (DDL 表記) を `型対応` entity 経由でドメイン型に解決した結果を流し込んでいる。クラス名・属性名はテーブル設計書の日本語をそのまま使い、型のみドメイン層の表記 (string / integer / date) に置き換える。

```mermaid
classDiagram
{% for tbl_id, rows in 列_with_ドメイン型 | groupby('テーブルID') %}
class `{{ tbl_id | safe }}` {
{% for row in rows %}
  {{ row.列.名前 | safe }} : {{ row.型情報.ドメイン型 | safe }}{% if row.列.主キー %} [PK]{% elif row.列.参照 %} [FK]{% endif +%}
{% endfor %}
}
{% endfor %}
{% for t in テーブル %}
{% for c in t.列 if c.参照 %}
`{{ t.id | safe }}` --> `{{ c.参照.テーブル | safe }}` : {{ c.名前 | safe }}
{% endfor %}
{% endfor %}
```

## ER 図 (Mermaid erDiagram)

```mermaid
erDiagram
{% for t in テーブル %}
"{{ t.id | safe }}" {
{% for c in t.列 %}
  {{ c.型 | safe }} {{ c.名前 | safe }}{% if c.主キー %} PK{% elif c.参照 %} FK{% endif +%}
{% endfor %}
}
{% endfor %}
{% for t in テーブル %}
{% for c in t.列 if c.参照 %}
"{{ t.id | safe }}" }o--|| "{{ c.参照.テーブル | safe }}" : "{{ c.名前 | safe }}"
{% endfor %}
{% endfor %}
```
