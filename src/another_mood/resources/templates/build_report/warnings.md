# Warnings

{% for d in diagnostics %}
{% if d.file %}**{{ d.file }}{% if d.line %}:{{ d.line }}{% endif %}{% if d.column %}:{{ d.column }}{% endif %}**

{% endif %}{{ d.message }}

{% if d.snippet %}
{{ code_fenced(d.snippet) }}

{% endif %}
{% endfor %}
