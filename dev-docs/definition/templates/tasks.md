# タスクカタログ

Phase 8 以降の残タスクを機能カテゴリ別に整理したもの。各タスクは実装箇所と仕様ドキュメントを併記する。フェーズ別の順序は [roadmap.md](roadmap.md) を参照。

{% for category in categories %}
## {{ category.id }}. {{ category.title }}

**実装箇所:**
{% for path in category.impl_paths %}
- `{{ path }}`
{%- endfor %}
{% if category.spec %}
**仕様:** [{{ category.spec }}](prose/{{ category.spec }})
{% endif %}

| ID | タスク | 備考 | Phase | Done |
|---|---|---|---|---|
{% for task in category.tasks -%}
| {{ task.id }} | {{ task.title }} | {{ task.note | replace('\n', ' ') | trim }} | {{ task.phase }} | {{ "✅" if task.done else "" }} |
{% endfor %}
{% endfor %}
