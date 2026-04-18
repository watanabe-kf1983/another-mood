# ロードマップ

Phase 1〜7 で TypeScript 実装からの移行、自己ドッグフーディング基盤、Hugo 連携、example-project 同等機能、メタドキュメンテーションまでを完了した（詳細は git 履歴参照）。Phase 8 以降の計画をフェーズ別に示す。

タスクを機能カテゴリ別に見る場合は [tasks.md](tasks.md) を参照。タスク ID の先頭文字が機能カテゴリに対応する。

{% for group in tasks_by_phase | sort(attribute='phase') %}
## Phase {{ group.phase }}

| ID | タスク | 備考 | Done |
|---|---|---|---|
{% for task in group.tasks -%}
| {{ task.id }} | {{ task.title }} | {{ task.note | replace('\n', ' ') | trim }} | {{ "✅" if task.done else "" }} |
{% endfor %}
{% endfor %}
