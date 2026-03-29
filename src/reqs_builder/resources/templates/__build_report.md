# Build Report

{% if diagnostics %}
## Problems

{% for d in diagnostics %}
**{{ d.file }}{% if d.line %}:{{ d.line }}{% endif %}{% if d.column %}:{{ d.column }}{% endif %}**

{{ d.message }}

{% endfor %}
{% endif %}
{% if errors %}
## Errors

{% for error in errors %}
{{ error.message }}

{% if error.traceback %}
```
{{ error.traceback }}```

{% endif %}
{% endfor %}
{% endif %}
