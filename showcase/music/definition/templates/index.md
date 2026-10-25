# {{ catalog.title }}

{{ node(path="/prose/background") | render("prose.md") | under_heading("#") }}

{# The front matter is one record, `catalog`, read straight from the root
   along with two plain values beside it, `updated_at` and `moods` (the
   single-record pattern). The `series` map arrives as a list with each key
   lifted into `id`, like any other map. #}
*Kept by {{ catalog.maintainer }}; last revised {{ updated_at }}. Moods: {{ moods | join(", ") }}.*

## Featured

{% for entry in featured_albums %}
- {{ node("album_tracklist", entry.album_id) | link }} ({{ entry.album.year }}) - {{ entry.note }}
{% endfor %}

## Series

{% for series in catalog.series %}
- **{{ series.name }}** ({{ series.id }}) - {{ series.description }}
{% for entry in series.albums %}
  - {{ node("album_tracklist", entry.album_id) | link }}
{% endfor %}
{% endfor %}

## Editor's picks

Signed by {{ catalog.editorial.editor }}.

{% for pick in catalog.editorial.picks %}
- {{ node("tracks", pick.track_id).title }} - {{ pick.comment }}
{% endfor %}

## Artists

{# Two-loop pattern: the list links each artist, the second loop renders
   the detail where `file_per` puts it (inline here, or on its own page). #}
{% for artist in artist_discography %}
- {{ artist | link }}{% if artist.country %} - {{ artist.country }}{% endif +%}
{% endfor %}

{% for artist in artist_discography %}
{{- artist | render("artist-detail.md") | under_heading("##") -}}
{% endfor %}

## Albums by genre

{% for entry in genres_with_albums %}
- **{{ entry.genre.name }}**
{% for album in entry.albums | sort(attribute="year") %}
  - {{ node("album_tracklist", album.id) | link }} ({{ album.year }})
{% endfor %}
{% endfor %}

{% for album in album_tracklist %}
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
- {{ node("album_tracklist", album.id) | link }} ({{ album.year }})
{% endfor %}

## Live tracks

Live takes, wherever they were released.

| Track | Album |
|-------|-------|
{% for t in live_tracks %}
| {{ t.title }} | {{ t.album_id }} |
{% endfor %}

## Band rosters

Who plays what, across every act.

| Artist | Member | Instrument |
|--------|--------|------------|
{% for row in artist_members %}
| {{ row.artist.name }} | {{ row.member.name }} | {{ row.member.instrument }} |
{% endfor %}

## All releases

Every act on the roster, including those yet to release a record.

{% for row in artist_album_pairs_all %}
- **{{ row.name }}** ({{ row.id }}){% if row.album %} - {{ row.album.title }} ({{ row.album.year }}){% else %} - _no releases yet_{% endif +%}
{% endfor %}

## Track index

| Track | Album | Artist |
|-------|-------|--------|
{% for row in tracks_with_artist %}
| {{ row.title }} | {{ row.album.title }} | {{ row.album.artist.name }} |
{% endfor %}

## Playlists

{% for pl in playlists_with_tracks %}
### {{ pl.name }}

*Curated by {{ code_inline(pl.curator) }}.* {{ pl.description }}

{% for entry in pl.entries | sort(attribute="position") %}
{{ entry.position }}. {{ entry.track.title }}
{% endfor %}

{% endfor %}
