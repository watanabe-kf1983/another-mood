# Build Error

{% for error in __errors %}
**{{ error.source }}**

{{ error.message }}

<details>
<summary>Traceback</summary>

```
{{ error.traceback }}```

</details>

{% endfor %}
