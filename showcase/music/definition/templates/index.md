# Music Catalog

{% filter under_heading("#") %}
{% mood_view "prose.md" with node(path="/prose/background") %}
{% endfilter %}

## Artists

{% for artist in artist_discography %}
- {{ artist | link }}{% if artist.country %} - {{ artist.country }}{% endif +%}
{% endfor %}

{% for artist in artist_discography %}
{% filter under_heading("##") %}
{% mood_view "artist-detail.md" with artist %}
{% endfilter %}
{% endfor %}

## Albums by genre

The genre name comes straight from the `genres_with_albums` view, which
reads the grouped `albums_by_genre` view and joins `genres` onto it (a
query-to-query reference) - so the template no longer re-joins genres itself.

{% for entry in genres_with_albums %}
- **{{ entry.genre.name }}**
{% for album in entry.albums | sort(attribute="year") %}
  - {{ node("album_tracklist", album.id) | link }} ({{ album.year }})
{% endfor %}
{% endfor %}

{% for album in album_tracklist %}
{% filter under_heading("##") %}
{% mood_view "album-detail.md" with album %}
{% endfilter %}
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

These albums are surfaced by the `live_albums` query (`where: { id: { startswith: live_ } }`).

{% for album in live_albums %}
- {{ node("album_tracklist", album.id) | link }} ({{ album.year }})
{% endfor %}

## Live tracks

Tracks whose title contains "Live" (`where: { title: { contains: Live } }`).

| Track | Album |
|-------|-------|
{% for t in live_tracks %}
| {{ t.title }} | {{ t.album_id }} |
{% endfor %}

## Band rosters

Flattened from the `artists.members` nested map.

| Artist | Member | Instrument |
|--------|--------|------------|
{% for row in artist_members %}
| {{ row.artist_name }} | {{ row.member.name }} | {{ row.member.instrument }} |
{% endfor %}

## Discography (LEFT-join view)

Every artist appears once, including those with no released albums (`artist_album_pairs_all` uses `flatten: { preserve_empty: true }`).

{% for row in artist_album_pairs_all %}
- **{{ row.name }}** ({{ row.id }}){% if row.album %} - {{ row.album.title }} ({{ row.album.year }}){% else %} - _no releases yet_{% endif +%}
{% endfor %}

## Full track index

Each track joined to its album and the album's artist (`tracks_with_artist`, multi-join list form).

| Track | Album | Artist |
|-------|-------|--------|
{% for row in tracks_with_artist %}
| {{ row.title }} | {{ row.album.title }} | {{ row.artist.name }} |
{% endfor %}

## Playlists

{% for pl in playlists %}
### {{ pl.name }}

*Curated by {{ code_inline(pl.curator) }}.* {{ pl.description }}

{% set entries = playlist_tracks | selectattr("playlist_id", "equalto", pl.id) | sort(attribute="position") %}
{% for entry in entries %}
{{ entry.position }}. {{ node("tracks", entry.track_id).title }}
{% endfor %}

{% endfor %}
