# User interface design

Shows the screens this system presents to its users: the screen list, the screen flow diagram, and a screen definition (layout, input and output items, actions) for each screen.

## Screens

| ID | Screen | Category | Use cases | Description |
|----|--------|----------|-----------|-------------|
{% for s in this %}
  {{- "" }}| {{ s.id }}
  {{- "" }} | {{ s | link(s.name) }}
  {{- "" }} | {{ s.category | capitalize }}
  {{- "" }} | {% for u in s.use_cases %}{{ node("srs", "requirements", "functional", u.id) | link(u.id) }} {{ node("use_cases", u.id).name }}{% if not loop.last %}, {% endif %}{% endfor %}
  {{- "" }} | {{ s.description | in_cell }}
  {{- "" }} |
{% endfor %}

Of the categories, a menu is an entry point that leads to other screens, an entry screen takes input and creates data, a list screen searches and lists several records, and a detail screen shows one record in full. The menu comes first, then the screens in the order of their use cases.

## Screen flow

{# state = screen, transition = action.transitions. Screens are not bundled
   into a composite state per use case: screens and use cases are
   many-to-many, and the same state cannot sit in two composite states. The
   screen list carries the mapping from screens to use cases. Exits
   (transitions to [*]) are not drawn: a user can stop on any screen, and
   drawing them would send a line out of every screen and make the diagram
   unreadable. Links cannot be made from inside a code fence, so the way to the
   use cases is in the screen list too. #}
{% filter dedent %}
  ```mermaid
  stateDiagram-v2
    direction TB
  {% for s in this if s.category == "menu" %}
    [*] --> {{ s.id | safe }}
  {% endfor %}
  {% for s in this %}
    {{ s.id | safe }} : {{ s.name | safe }}
  {% endfor %}
  {% for s in this %}
    {% for a in s.actions %}
      {% for t in a.transitions %}
        {{ s.id | safe }} --> {{ t.to | safe }} : {{ a.name | safe }}{% if t.condition %} [{{ t.condition | safe }}]{% endif +%}
      {% endfor %}
    {% endfor %}
  {% endfor %}
  ```
{% endfilter %}

Actions that complete within a screen (searching, adding a line and the like) do not change the screen and so do not appear in this diagram.

{{ node(path="/prose/sdd/user_interface_design").content | relink }}

## Screen definitions

For each screen, its layout, input and output items, and actions. What a screen holds is defined by the tables of input and output items and actions; the layout is a drawing of their arrangement. There are {{ this | length }} screens, {% for s in this %}{{ s | link(s.name) }}{% if not loop.last %}, {% endif %}{% endfor %}, in the same order as the screen list.

{% for s in this %}
{{ s | render("screen.md") | under_heading("###") -}}
{% endfor %}
