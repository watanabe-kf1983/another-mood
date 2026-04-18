# Phase 8 候補タスク

ロードマップ Phase 8 開始時の整理。フェーズ振り分け前の MECE タスクリスト。
機能別に分類し、各タスクは実装箇所と仕様ドキュメントを併記する。

{% for category in phase8_categories %}
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
| {{ task.id }} | {{ task.title }} | {{ task.note }} | {{ task.phase }} | {{ "✅" if task.done else "" }} |
{% endfor %}
{% endfor %}

## フェーズ別

機能別にネストしたタスクを phase でグループ化して再構成した横断ビュー。タスク ID の先頭文字が機能カテゴリに対応する。

{% for group in tasks_by_phase | sort(attribute='phase') %}
### Phase {{ group.phase }}

| ID | タスク | 備考 | Done |
|---|---|---|---|
{% for task in group.tasks -%}
| {{ task.id }} | {{ task.title }} | {{ task.note }} | {{ "✅" if task.done else "" }} |
{% endfor %}
{% endfor %}
