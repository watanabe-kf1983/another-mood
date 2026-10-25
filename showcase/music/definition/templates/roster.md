# Roster

## Artists

{% for artist in artists %}
{{- artist | render("artist-detail.md") | under_heading("##") -}}
- {{ artist | link }}{% if artist.country %} - {{ artist.country }}{% endif +%}
{% endfor %}

## Band rosters

Who plays what, across every act.

| Artist | Member | Instrument |
|--------|--------|------------|
{% for row in members %}
| {{ row.artist.name }} | {{ row.member.name }} | {{ row.member.instrument }} |
{% endfor %}

## All releases

Every act on the roster, including those yet to release a record.

{% for row in releases %}
- **{{ row.name }}** ({{ row.id }}){% if row.album %} - {{ row.album.title }} ({{ row.album.year }}){% else %} - _no releases yet_{% endif +%}
{% endfor %}
