# Another Mood showcases

Sample projects built with [Another Mood](https://github.com/watanabe-kf1983/another-mood), rendered as it renders them. Each entry links to the built site and to its sources on GitHub.

{# Links are relative to the site root, where `make pages` publishes this
   page alone; in the project's own build output they do not resolve. #}
{% for blueprint in blueprints %}
[{{ blueprint.name }}](showcase/{{ blueprint.name | as_url }}/) · [sources](https://github.com/watanabe-kf1983/another-mood/tree/main/showcase/{{ blueprint.name | as_url }})
: {{ blueprint.description }}

{% endfor %}

---

Built from {{ build_info("vars.git_commit_id", "(dev)") }} by {{ build_info("processor.name") }} {{ build_info("processor.version") }}
