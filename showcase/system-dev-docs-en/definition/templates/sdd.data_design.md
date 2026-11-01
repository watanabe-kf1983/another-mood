# Data design

Shows the data this system handles as a {{ logical_data_model | link("logical data model") }}, and which use case reads and writes which entity in the {{ crud_matrix | link("CRUD matrix") }}.

{{ logical_data_model | render("logical_data_model.md") | under_heading("#") }}

{{ crud_matrix | render("crud_matrix.md") | under_heading("#") }}
