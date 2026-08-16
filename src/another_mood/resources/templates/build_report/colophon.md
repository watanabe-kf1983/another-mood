{% if build_info %}
## Build info

| Key | Value |
|---|---|
{% for key, value in build_info | dictsort %}
| {{ code_inline(key) }} | {{ value | in_cell }} |
{% endfor %}
{% endif %}
