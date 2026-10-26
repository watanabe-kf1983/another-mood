# Appendices

Lists the assumptions and dependencies of this document, and decomposes the inside of {{ (node("processes") | rejectattr("parent_id") | first).name }}, shown in the {{ node("srs", "introduction", "business_context") | link("business context") }}, step by step as the {{ business_model | link("business model") }}.

{{ prose | child("srs/appendices") | render("prose.md") | under_heading("#") }}

{{ business_model | render("business_model.md") | under_heading("#") }}
