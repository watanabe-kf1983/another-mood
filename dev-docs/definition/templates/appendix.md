{{ content | relink }}
{% for record in node("prose") | sort(attribute="order_key") if record.id is startingwith("90-appendix/") and record.id != "90-appendix/index" %}
{{ "  " * (record.depth - 3) }}- {{ record | link }}
{% endfor %}
