# ロードマップ

Phase 15 までは完了している（詳細は git 履歴と {{ node(path="/tasks") | link("タスクカタログ") }} を参照）。Phase 16 以降のタスクをフェーズ別に示す。

タスクを機能カテゴリ別に見る場合は {{ node(path="/tasks") | link("タスクカタログ") }} を参照。タスク ID の先頭文字が機能カテゴリに対応する。

{% for group in this | sort(attribute='phase') %}
## Phase {{ group.phase }}{{ group | anchor }}

| ID | タスク | Proposal | 備考 | Done |
|---|---|---|---|---|
{% for row in group.tasks %}
    {{- "" }}| {{ node("tasks", row.id, "tasks", row.task.id) | link(row.task.id) }}
    {{- "" }} | {{ row.task.title }}
    {{- "" }} | {% if row.task.proposal %}{{ node(path="/prose/" ~ row.task.proposal) | link("→") }}{% endif %}
    {{- "" }} | {{ row.task.note | replace('\n', ' ') | trim }}
    {{- "" }} | {{ "✅" if row.task.done else "" }}
    {{- "" }} |
{% endfor %}

{% endfor %}
