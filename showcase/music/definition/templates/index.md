# {{ catalog.title }}

{{ node(path="/prose/background") | render("prose.md") | under_heading("#") }}

{# The front matter is one record, `catalog`, read straight from the root
   along with two plain values beside it, `updated_at` and `moods` (the
   single-record pattern). The `series` map arrives as a list with each key
   lifted into `id`, like any other map. #}
*Kept by {{ catalog.maintainer }}; last revised {{ updated_at }}. Moods: {{ moods | join(", ") }}.*

## Featured

{% for entry in featured_albums %}
- {{ node("discography", "albums", entry.album_id) | link }} ({{ entry.album.year }}) - {{ entry.note }}
{% endfor %}

## Series

{% for series in catalog.series %}
- **{{ series.name }}** ({{ series.id }}) - {{ series.description }}
{% for entry in series.albums %}
  - {{ node("discography", "albums", entry.album_id) | link }}
{% endfor %}
{% endfor %}

## Editor's picks

Signed by {{ catalog.editorial.editor }}.

{% for pick in catalog.editorial.picks %}
- {{ node("tracks", pick.track_id).title }} - {{ pick.comment }}
{% endfor %}

## Contents

{# Each page is a nested view's holder (`roster`, `discography`,
   `curated`): the views named `roster.*` and so on gather under it.
   Two-loop pattern: link here, render below where `file_per` puts it. #}
- {{ roster | link("Roster") }} - the artists, their line-ups and releases
- {{ discography | link("Discography") }} - every album, by genre, label and track
- {{ curated | link("Playlists") }} - curated running orders

{{ roster | render("roster.md") | under_heading("#") }}
{{ discography | render("discography.md") | under_heading("#") }}
{{ curated | render("curated.md") | under_heading("#") }}
