# {{ name }}

{% if parent_id %}
Part of {{ node("discography", "genres", parent_id) | link }}.

{% endif %}
{% if subgenres %}
## Subgenres

  {% for sub in subgenres %}
- {{ node("discography", "genres", sub.id) | link }}
  {% endfor %}

{% endif %}
## Albums

{% if albums %}
  {% for album in albums | sort(attribute="year") %}
- {{ node("discography", "albums", album.id) | link }} ({{ album.year }}) - {{ node("roster", "artists", album.artist_id) | link }}
  {% endfor %}
{% else %}
_No albums filed directly under {{ name }}._
{% endif %}
