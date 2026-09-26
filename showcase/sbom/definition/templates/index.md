# Another Mood SBOM

The software bill of materials of {{ root_component.name }} — every package it installs at runtime, with licenses and the dependency graph between them. The data is a CycloneDX SBOM from a generator, reshaped just enough to fit the schema language; every page here is derived from it by views. {{ node("prose", "generating") | link("How the data was made") }} walks through the steps.

{{ node("prose", "generating") | render("prose.md") }}

## Components

### Direct dependencies

Required by {{ root_component.name }} itself.

| Component | Version | License |
|-----------|---------|---------|
{% for c in component if c.required_by_root %}
{{- c | render("component.md") -}}
| {{ c | link }} | {{ c.version }} | {% for lic in c.licenses %}{{ lic.license.id or lic.license.name or lic.expression }}{% if not loop.last %}, {% endif %}{% endfor %} |
{% endfor %}

### Transitive dependencies

Pulled in by other components.

| Component | Version | License |
|-----------|---------|---------|
{% for c in component if not c.required_by_root %}
{{- c | render("component.md") -}}
| {{ c | link }} | {{ c.version }} | {% for lic in c.licenses %}{{ lic.license.id or lic.license.name or lic.expression }}{% if not loop.last %}, {% endif %}{% endfor %} |
{% endfor %}

## Licenses

### By SPDX identifier

| License | Components |
|---------|------------|
{% for entry in spdx_ledger %}
| {{ entry.id }} | {% for c in entry.components %}{{ node("component", c.id) | link }}{% if not loop.last %}, {% endif %}{% endfor %} |
{% endfor %}

### Other declarations

Licenses declared without an SPDX identifier: a free-form name, or an SPDX expression combining several licenses.

| Component | Declared as | License |
|-----------|-------------|---------|
{% for row in other_licenses %}
| {{ node("component", row.id) | link }} | {% if row.lic.expression %}expression{% else %}name{% endif %} | {{ row.lic.expression or row.lic.license.name }} |
{% endfor %}
