# タスクカタログ

残タスクを機能カテゴリ別に整理したもの。各タスクは実装箇所と仕様ドキュメントを併記する。フェーズ別の順序は {{ node("/roadmap") | link("ロードマップ") }} を参照。完了済みタスクは記載しない（git log を参照）。

{% for category in this %}
## {{ category.id }}. {{ category.title }}

**実装箇所:**

{% for path in category.impl_paths %}
- {{ code_inline(path) }}
{% endfor %}

{% if category.spec %}
**仕様:** {{ node("/prose/" ~ category.spec) | link }}
{% endif %}

| ID | タスク | Proposal | 備考 | Phase | Done |
|---|---|---|---|---|---|
{% for task in category.tasks %}
    {{- "" }}| {{ task.id }}
    {{- "" }} | {{ task.title }}
    {{- "" }} | {% if task.proposal %}[→](prose/{{ task.proposal | as_url }}){% endif %}
    {{- "" }} | {{ task.note | replace('\n', ' ') | trim }}
    {{- "" }} | {{ task.phase }}
    {{- "" }} | {{ "✅" if task.done else "" }}
    {{- "" }} |
{% endfor %}

{% endfor %}
