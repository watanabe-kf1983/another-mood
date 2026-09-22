{#- 設計書「データ設計」章の後半。主題は章専用の CRUDマトリクス ビュー (ユースケース に
    データアクセス を join したもの) で、web edition ではこの節が 1 ページになる。
    行は主題の各行 (ユースケースの記述順 = 業務の時系列)、列は node("エンティティ")
    (記述順 = リソース → イベントの作成順)。セルは行の アクセス を列のエンティティ ID
    で突合して 操作 を出す。同じ (ユースケース, エンティティ) の組は 1 件の約束なので
    for で回しても出るのは高々 1 件。

    表の下の読み方は、列ごとに C / U / D の有無を数えて文にする。IPA の CRUD 図の
    使い方 (どのユースケースからも作られない・更新されないエンティティの検出) を、
    表を目で追わなくても済むように文として導出しておくもの。集計は namespace で持つ
    (テンプレート内でリストに追加する手段が無いので、名前を「、」で繋いだ文字列に
    畳む)。集計文の言い回しはどの題材でも成り立つ形に留め、この題材に固有の解釈
    (なぜ入荷と販売は更新されないか等) は prose レコード
    (contents/設計書/CRUDマトリクス.md) に置いて表の下に埋め込む (主題の部分木の外
    なので render ではなく content | relink)。 -#}
{% set entities = node("エンティティ") %}
# CRUD マトリクス

どのユースケースがどのエンティティを読み書きするかを示す。行はユースケース (業務の時系列順)、列はエンティティ (エンティティ一覧と同じ順) で、セルの文字は C (作成)、R (参照)、U (更新)、D (削除) を表す。空欄は、そのユースケースがそのエンティティに触れないことを表す。

| ユースケース | {% for e in entities %}{{ e | link(e.名前) }} | {% endfor +%}
|--------------|{% for e in entities %}---|{% endfor +%}
{% for uc in this %}
| {{ node("ユースケース記述", uc.id) | link(uc.id) }} {{ uc.名前 }} | {% for e in entities %}{% for a in uc.アクセス if a.エンティティ == e.id %}{{ a.操作 }}{% endfor %} | {% endfor +%}
{% endfor %}
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

行を横に読むと、そのユースケースが触るエンティティと操作が分かる。列を縦に読むと、そのエンティティを誰が作り、誰が更新するかが分かる。{% if ns.never_created %}どのユースケースからも作成されないのは{{ ns.never_created }}である。{% else %}すべてのエンティティは、いずれかのユースケースで作成される。{% endif %}作成の後に更新されないのは{{ ns.never_updated }}で、{% if ns.deleted %}削除されるのは{{ ns.deleted }}である。{% else %}削除されるエンティティは無い。{% endif +%}

{{ node(path="/prose/設計書/CRUDマトリクス").content | relink }}
