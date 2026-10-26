# System context

Shows the boundary of this system and its relations with the users and external systems outside it.

{% filter dedent %}
  ```mermaid
  flowchart LR
  {% for a in node("actors") if a.kind == "person" %}
    {{ a.id | safe }}("{{ a.name | safe }}")
  {% endfor %}
  subgraph system["{{ node(path="/system").name | safe }}"]
    {% for uc in this %}
      {{ uc.id | safe }}(["{{ uc.name | safe }}"])
    {% endfor %}
  end
  {% for a in node("actors") if a.kind == "external_system" %}
    {{ a.id | safe }}[["{{ a.name | safe }}"]]
  {% endfor %}
  {% for uc in this %}
    {% for a in uc.actors %}
      {{ a.id | safe }} --- {{ uc.id | safe }}
    {% endfor %}
  {% endfor %}
  ```
{% endfilter %}

This system is responsible only for what lies inside the boundary; the parts of the users' work that happen outside it are not its responsibility.

The content of each use case is in the {{ node("srs", "introduction", "product_functions") | link("product functions") }} of the requirements specification and its functional requirements section, and the requirements on the interactions across the boundary themselves are among the {{ node("srs", "requirements", "non_functional", "external_interface") | link("external interface requirements") }}.
