# Music Catalog

A fictional sampler catalog used to demonstrate Another Mood. Browse by artist or by album below, follow the genre tree to see how groupings cascade, and scroll on for cross-cutting views (live recordings, member rosters, the full track index, playlists).

## Artists

{%- for artist in artist_discography %}
- [{{ artist.name }}](artist-detail/{{ artist.id }}.md){% if artist.country %} - {{ artist.country }}{% endif %}
{%- endfor %}

{%- for artist in artist_discography -%}
{% mood_view "artist-detail" with artist %}
{%- endfor %}

## Albums by genre

{%- for entry in albums_by_genre %}

### {{ genres | selectattr("id", "equalto", entry.genre_id) | map(attribute="name") | first }}
{% for album in entry.albums | sort(attribute="year") %}
- [{{ album.title }}](album-detail/{{ album.id }}.md) ({{ album.year }})
{%- endfor %}
{%- endfor %}

{%- for album in album_tracklist -%}
{% mood_view "album-detail" with album %}
{%- endfor %}

## Genre hierarchy

{% for genre in genres if not genre.parent_id -%}
- {{ genre.name }}
{%- for child in genres if child.parent_id == genre.id %}
  - {{ child.name }}
{%- for grandchild in genres if grandchild.parent_id == child.id %}
    - {{ grandchild.name }}
{%- endfor %}
{%- endfor %}
{% endfor %}

## Labels

| Label | Country | Founded |
|-------|---------|---------|
{% for label in labels -%}
| {{ label.name }} | {{ label.country }} | {{ label.founded }} |
{% endfor %}

## Concert recordings

These albums are surfaced by the `live_albums` query (`where: { id: { startswith: live_ } }`).

{% for album in live_albums -%}
- [{{ album.title }}](album-detail/{{ album.id }}.md) ({{ album.year }})
{% endfor %}

## Live tracks

Tracks whose title contains "Live" (`where: { title: { contains: Live } }`).

| Track | Album |
|-------|-------|
{% for t in live_tracks -%}
| {{ t.title }} | {{ t.album_id }} |
{% endfor %}

## Band rosters

Flattened from the `artists.members` nested map.

| Artist | Member | Instrument |
|--------|--------|------------|
{% for row in artist_members -%}
| {{ row.artist_name }} | {{ row.member.name }} | {{ row.member.instrument }} |
{% endfor %}

## Discography (LEFT-join view)

Every artist appears once, including those with no released albums (`artist_album_pairs_all` uses `flatten: { preserve_empty: true }`).

{% for row in artist_album_pairs_all -%}
- **{{ row.name }}** ({{ row.id }}){% if row.album %} - {{ row.album.title }} ({{ row.album.year }}){% else %} - _no releases yet_{% endif %}
{% endfor %}

## Full track index

Each track joined to its album and the album's artist (`tracks_with_artist`, multi-join list form).

| Track | Album | Artist |
|-------|-------|--------|
{% for row in tracks_with_artist -%}
| {{ row.title }} | {{ row.album.title }} | {{ row.artist.name }} |
{% endfor %}

## Playlists

{% for pl in playlists %}
### {{ pl.name }}

*Curated by `{{ pl.curator }}`.* {{ pl.description }}

{% set entries = playlist_tracks | selectattr("playlist_id", "equalto", pl.id) | sort(attribute="position") -%}
{% for entry in entries -%}
{{ entry.position }}. {{ tracks | selectattr("id", "equalto", entry.track_id) | map(attribute="title") | first }}
{% endfor %}
{% endfor %}

{%- for record in prose -%}
{% mood_view "prose" with record %}
{%- endfor %}
