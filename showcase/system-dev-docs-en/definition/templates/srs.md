# Software Requirements Specification

The software requirements specification for {{ node(path="/system").description }}.

- {{ introduction | link("Introduction") }}
- {{ glossary | link("Glossary") }}
- {{ requirements | link("Requirements") }}
- {{ verification | link("Verification") }}
- {{ appendices | link("Appendices") }}

{{ introduction | render("srs.introduction.md") | under_heading("#") }}

{{ glossary | render("glossary.md") | under_heading("#") }}

{{ requirements | render("srs.requirements.md") | under_heading("#") }}

{{ verification | render("srs.verification.md") | under_heading("#") }}

{{ appendices | render("srs.appendices.md") | under_heading("#") }}
