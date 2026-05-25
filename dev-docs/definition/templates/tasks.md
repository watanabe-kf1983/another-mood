# タスクカタログ

残タスクを機能カテゴリ別に整理したもの。各タスクは実装箇所と仕様ドキュメントを併記する。フェーズ別の順序は [roadmap.md](roadmap.md) を参照。完了済みタスクは記載しない（git log を参照）。

{% for category in categories %}
## {{ category.id }}. {{ category.title }}

**実装箇所:**
{% for path in category.impl_paths %}
- {{ code_inline(path) }}
{%- endfor %}
{% if category.spec %}
**仕様:** [{{ category.spec }}](prose/{{ category.spec | as_url }})
{% endif %}

| ID | タスク | Proposal | 備考 | Phase | Done |
|---|---|---|---|---|---|
{% for task in category.tasks -%}
| {{ task.id }} | {{ task.title }} | {% if task.proposal %}[→](prose/{{ task.proposal | as_url }}){% endif %} | {{ task.note | replace('\n', ' ') | trim }} | {{ task.phase }} | {{ "✅" if task.done else "" }} |
{% endfor %}
{% endfor %}
