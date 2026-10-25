# Roster

## Artists

{% for artist in artists %}
{{- artist | render("artist-detail.md") | under_heading("##") -}}
{% set years = artist.albums | map(attribute="year") | list %}
- {{ artist | link }}{% if artist.country %} - {{ artist.country }}{% endif %}
  {{- "" }} - {% if years %}{{ years | length }} album{{ "s" if years | length > 1 }}, {{ years | min }}{% if years | max != years | min %}-{{ years | max }}{% endif %}{% else %}_no releases yet_{% endif +%}
{% endfor %}

## Players by instrument

{% for entry in instruments %}
- **{{ entry.member.instrument | capitalize }}**: {% for player in entry.players %}{{ player.member.name }} ({{ node("roster", "artists", player.id) | link }}){% if not loop.last %}, {% endif %}{% endfor +%}
{% endfor %}
