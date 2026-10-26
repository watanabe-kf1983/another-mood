# Software Design Document

The software design document for {{ node(path="/system").description }}.

- {{ introduction | link("Introduction") }}
- {{ system_context | link("System context") }}
- {{ architecture | link("System architecture") }}
- {{ data_design | link("Data design") }}
- {{ user_interface_design | link("User interface design") }}

{{ introduction | render("sdd.introduction.md") | under_heading("#") }}

{{ system_context | render("system_context.md") | under_heading("#") }}

{{ architecture | render("architecture.md") | under_heading("#") }}

{{ data_design | render("sdd.data_design.md") | under_heading("#") }}

{{ user_interface_design | render("user_interface_design.md") | under_heading("#") }}
