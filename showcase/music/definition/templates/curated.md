# Playlists

{% for pl in playlists %}
## {{ pl.name }}

*Curated by {{ code_inline(pl.curator) }}.* {{ pl.description }}

  {% for entry in pl.entries | sort(attribute="position") %}
{{ entry.position }}. {{ node("discography", "albums", entry.track.album_id, "tracks", entry.track.id) | link }} from *{{ node("discography", "albums", entry.track.album_id) | label }}*
  {% endfor %}

{% endfor %}
