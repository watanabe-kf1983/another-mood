# Playlists

{% for pl in playlists %}
## {{ pl.name }}

*Curated by {{ code_inline(pl.curator) }}.* {{ pl.description }}

{% for entry in pl.entries | sort(attribute="position") %}
{{ entry.position }}. {{ entry.track.title }}
{% endfor %}

{% endfor %}
