# {{ name }}

**Country:** {{ country }}  
**Founded:** {{ founded }}

## Releases

{% for album in albums | sort(attribute="year") %}
- {{ node("discography", "albums", album.id) | link }} ({{ album.year }}) - {{ node("roster", "artists", album.artist_id) | link }}
{% endfor %}
