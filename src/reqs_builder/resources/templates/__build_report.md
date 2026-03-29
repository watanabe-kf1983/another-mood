# Build Report

{% for error in errors %}
{% if error.source %}**{{ error.source }}{% if error.lineno %}, line {{ error.lineno }}{% endif %}**{% endif %}

{{ error.message }}

<details>
<summary>Traceback</summary>

```
{{ error.traceback }}```

</details>

{% endfor %}
