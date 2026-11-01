# {{ system.name }}

This project is an Another Mood sample that derives two documents, a Software Requirements Specification (SRS) and a Software Design Document (SDD), from a single data source. The subject is {{ system.description }}. Each chapter of the design document refers to the use cases, terms and requirements of the requirements specification, so a correction to one document carries over to the other.

- {{ srs | link("Software Requirements Specification") }} — the scope of the business, the glossary, the functional requirements per use case and the non-functional requirements, how each is verified, and the business model (a levelled data flow diagram)
- {{ sdd | link("Software Design Document") }} — the design decisions, the system boundary, the system architecture, the logical data model with its CRUD matrix, and the screens

The chapter structure of the two documents is one example, informed by ISO/IEC/IEEE 29148 and the IPA guides. Which documents to produce, and at what granularity, differs from project to project, so read the schema and the templates as a model to rewrite into the structure of your own project.

{{ srs | render("srs.md") | under_heading("#") }}

{{ sdd | render("sdd.md") | under_heading("#") }}
