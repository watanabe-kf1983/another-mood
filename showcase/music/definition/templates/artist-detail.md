# {{ name }}

{% if country %}**Country:** {{ country }}  {% endif +%}
{% if formed_year %}**Formed:** {{ formed_year }}{% endif +%}

{{ bio }}

## Members

{% if members %}
| Member | Instrument |
|--------|------------|
{% for m in members %}
| {{ m.name }} | {{ m.instrument }} |
{% endfor %}
{% else %}
_No active line-up on record._
{% endif %}

## Discography

{% if albums %}
{% for album in albums | sort(attribute="year") %}
- {{ node("album_tracklist", album.id) | link }} ({{ album.year }})
{% endfor %}
{% else %}
_No releases yet._
{% endif %}
