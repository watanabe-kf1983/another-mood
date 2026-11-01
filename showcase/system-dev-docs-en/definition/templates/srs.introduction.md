# Introduction

States the purpose and scope of this document and gives an overview of the product.

{{ prose | child("srs/introduction") | render("prose.md") | under_heading("#") }}

{{ business_context | render("business_context.md") | under_heading("#") }}

{{ product_functions | render("product_functions.md") | under_heading("#") }}

{{ users_and_external_systems | render("users_and_external_systems.md") | under_heading("#") }}

{{ prose | child("srs/constraints") | render("prose.md") | under_heading("#") }}
