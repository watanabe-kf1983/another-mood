# ロードマップ

Phase 1〜9 で TypeScript 実装からの移行、自己ドッグフーディング基盤、Hugo 連携、利用者リファレンス、メタドキュメンテーション、MCP サーバまでを完了した（詳細は git 履歴参照）。残タスクをフェーズ別に示す。

タスクを機能カテゴリ別に見る場合は {{ node("/tasks") | link("タスクカタログ") }} を参照。タスク ID の先頭文字が機能カテゴリに対応する。

{% for group in this | sort(attribute='phase') %}
## Phase {{ group.phase }}

| ID | タスク | Proposal | 備考 | Done |
|---|---|---|---|---|
{% for row in group.tasks %}
| {{ row.task.id }} | {{ row.task.title }} | {% if row.task.proposal %}[→](prose/{{ row.task.proposal | as_url }}){% endif %} | {{ row.task.note | replace('\n', ' ') | trim }} | {{ "✅" if row.task.done else "" }} |
{% endfor %}

{% endfor %}
