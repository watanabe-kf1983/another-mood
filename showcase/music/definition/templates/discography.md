# Discography

## Albums by genre

{% for entry in by_genre %}
- **{{ entry.genre.name }}**
{% for album in entry.albums | sort(attribute="year") %}
  - {{ node("discography", "albums", album.id) | link }} ({{ album.year }})
{% endfor %}
{% endfor %}

{% for album in albums %}
{{- album | render("album-detail.md") | under_heading("##") -}}
{% endfor %}

## Genre hierarchy

{% for genre in genres if not genre.parent_id %}
- {{ genre.name }}
{% for child in genres if child.parent_id == genre.id %}
  - {{ child.name }}
{% for grandchild in genres if grandchild.parent_id == child.id %}
    - {{ grandchild.name }}
{% endfor %}
{% endfor %}
{% endfor %}

## Labels

| Label | Country | Founded |
|-------|---------|---------|
{% for label in labels %}
| {{ label.name }} | {{ label.country }} | {{ label.founded }} |
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
| {{ row.title }} | {{ node("discography", "albums", row.album.id) | link(row.album.title) }} | {{ row.album.artist.name }} |
{% endfor %}
