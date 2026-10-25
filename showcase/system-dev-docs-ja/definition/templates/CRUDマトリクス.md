{% set entities = node("設計書", "データ設計", "論理データモデル") %}
# CRUD マトリクス

どのユースケースがどのエンティティを読み書きするかを示す。行はユースケース (業務の時系列順)、列はエンティティ (エンティティ一覧と同じ順) である。

| ユースケース | {% for e in entities %}{{ e | link(e.名前) }} | {% endfor +%}
|--------------|{% for e in entities %}---|{% endfor +%}
{# データアクセス に同じ (ユースケース, エンティティ) の組は高々 1 件しか無いので、
   セルの内側の for が出す 操作 も高々 1 つ。 #}
{% for uc in this %}
| {{ node("要求仕様書", "要求", "機能要求", uc.id) | link(uc.id) }} {{ uc.名前 }} | {% for e in entities %}{% for a in uc.アクセス if a.エンティティ == e.id %}{{ a.操作 }}{% endfor %} | {% endfor +%}
{% endfor %}
{# 表の下の集計文。IPA の CRUD 図の使い方 (どのユースケースからも作られない・
   更新されないエンティティの検出) を、表を目で追わなくても済むように文にする。
   テンプレートにはリストへ追加する手段が無いので、該当するエンティティの名前を
   「、」で繋いだ文字列として namespace に溜める。 #}
{% set ns = namespace(never_created="", never_updated="", deleted="") %}
{% for e in entities %}
  {% set flags = namespace(c=false, u=false, d=false) %}
  {% for uc in this %}
    {% for a in uc.アクセス if a.エンティティ == e.id %}
      {% if "C" in a.操作 %}{% set flags.c = true %}{% endif %}
      {% if "U" in a.操作 %}{% set flags.u = true %}{% endif %}
      {% if "D" in a.操作 %}{% set flags.d = true %}{% endif %}
    {% endfor %}
  {% endfor %}
  {% if not flags.c %}{% set ns.never_created = ns.never_created ~ ("、" if ns.never_created) ~ e.名前 %}{% endif %}
  {% if not flags.u %}{% set ns.never_updated = ns.never_updated ~ ("、" if ns.never_updated) ~ e.名前 %}{% endif %}
  {% if flags.d %}{% set ns.deleted = ns.deleted ~ ("、" if ns.deleted) ~ e.名前 %}{% endif %}
{% endfor %}

{% if ns.never_created %}どのユースケースからも作成されないのは{{ ns.never_created }}である。{% else %}すべてのエンティティは、いずれかのユースケースで作成される。{% endif %}作成の後に更新されないのは{{ ns.never_updated }}で、{% if ns.deleted %}削除されるのは{{ ns.deleted }}である。{% else %}削除されるエンティティは無い。{% endif +%}

{{ node(path="/prose/設計書/CRUDマトリクス").content | relink }}
