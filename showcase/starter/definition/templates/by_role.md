# {{ role }}

{% for member in members %}
- {{ node("members", member.id) | link }}
{% endfor %}
