# {{ title }}

**{{ year }}** &middot; {% if is_live %}Live recording{% else %}Studio album{% endif +%}

| Field | Value |
|-------|-------|
| Artist | {{ artist_id }} |
| Label | {{ label_id }} |
| Genre | {{ genre_id }} |

## Tracklist

| # | Title | Duration |
|---|-------|----------|
{% for track in tracks | sort(attribute="track_no") %}
    {{- "" }}| {{ track.track_no }}
    {{- "" }} | {{ track.title }}
    {{- "" }} | {{ '%d:%02d' | format(track.duration_sec // 60, track.duration_sec % 60) }}
    {{- "" }} |
{% endfor %}
