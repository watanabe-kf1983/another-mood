# Discography

## Albums

{% for album in albums %}
- {{ album | link }} ({{ album.year }}) - {{ node("roster", "artists", album.artist_id) | link }}
{% endfor %}

{% for album in albums %}
{{- album | render("album-detail.md") | under_heading("##") -}}
{% endfor %}

## Genres

{% for genre in genres if not genre.parent_id %}
- {{ genre | link }}
{% for child in genres if child.parent_id == genre.id %}
  - {{ child | link }}
{% for grandchild in genres if grandchild.parent_id == child.id %}
    - {{ grandchild | link }}
{% endfor %}
{% endfor %}
{% endfor %}

{% for genre in genres %}
{{- genre | render("genre-detail.md") | under_heading("##") -}}
{% endfor %}

## Labels

| Label | Country | Founded | Albums |
|-------|---------|---------|--------|
{% for label in labels %}
| {{ label | link }} | {{ label.country }} | {{ label.founded }} | {{ label.albums | length }} |
{% endfor %}

{% for label in labels %}
{{- label | render("label-detail.md") | under_heading("##") -}}
{% endfor %}

## Concert recordings

{% for album in live_albums %}
- {{ node("discography", "albums", album.id) | link }} ({{ album.year }})
{% endfor %}

## Live tracks

Live takes, wherever they were released.

| Track | Album | Artist |
|-------|-------|--------|
{% for row in live_tracks %}
| {{ row.title }} | {{ node("discography", "albums", row.album.id) | link(row.album.title) }} | {{ node("roster", "artists", row.album.artist.id) | link(row.album.artist.name) }} |
{% endfor %}
