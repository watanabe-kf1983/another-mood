# Build Failed - Another Mood

{% if diagnostics %}
## Problems

{% for d in diagnostics %}
**{{ d.file }}{% if d.line %}:{{ d.line }}{% endif %}{% if d.column %}:{{ d.column }}{% endif %}**

{{ d.message }}

{% if d.snippet %}
{{ code_fenced(d.snippet) }}

{% endif %}
{% endfor %}
{% endif %}
{% if errors %}
## Errors

{% for error in errors %}
{{ error.message }}

{% if error.traceback %}
{{ code_fenced(error.traceback) }}

{% endif %}
{% endfor %}
{% endif %}
