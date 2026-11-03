# Product Vision

The product vision and its background.

## What

A general-purpose tool that generates consistent, structured documents from any set of related objects and document templates.

It runs on Linux, macOS, and Windows. Windows users are among the primary targets.

## Why

### Background and history

The tool was first conceived as a way to reduce the labor of requirements definition.

The final deliverable of requirements definition (a list of functions at a granularity that function point analysis can measure) and the artifacts that substantiate it (ERDs, DFDs, CRUD matrices, use case descriptions) are all related to each other, and keeping them consistent by hand lets things slip.

Consistency checks are missed by humans and AI agents alike, so they should be mechanical; on that judgment, rather than letting Claude Code edit Markdown directly, we chose to describe the metadata in YAML and have a build tool validate and generate from it.

In the course of the discussion we realized what is essentially needed:

- Schema definitions such as DFDs and ERDs are nothing more than "configuration data"
- Consistency checks can be expressed generically as foreign key constraints
- What should be built is a **general-purpose document generator**

The requirements-definition deliverables themselves are offered as a showcase, not as a feature of the tool. `showcase/system-dev-docs-ja/` and `-en/` are the sample that derives two documents, a requirements specification and a design document, from one source, with each chapter of the design document referring into the requirements specification.

## Core Design Decision

### Separating data from views

The heart of this tool is the separation of data from views.

```
Data (YAML/Markdown) = Single Source of Truth
     ↓
Template A → Document A
Template B → Document B
Template C → Document C
```

Without the separation, inconsistencies like these arise:

- Document A says "the user is X"
- Document B says "the user is Y"

With the separation, the data is managed in one place and consistency is guaranteed.

#### Trade-off

This design has an unavoidable trade-off:

| Gained | Lost |
|---------|---------|
| Guaranteed consistency | Cognitive load |
| Multiple views | Learning cost |
| One place to change | The ease of "plain Markdown" |

The user has to keep asking:

- "Where does this data go?"
- "How do I fix the template?"

This demands a programmer's way of thinking, and the learning cost is high.

#### Absorbing the cognitive load with an AI agent

The trade-off's "cognitive load and learning cost" is resolved by pushing it onto an AI agent.

```
Before:        user → thinks about "where and how to write" → writes
With an agent: user → says only "what to write" → the AI agent writes it properly
```

The user concentrates on the content of the data; where and how to write it is decided and done by the AI agent.

- Guaranteed consistency → kept (data separated from views)
- Cognitive load → absorbed by the AI agent
- Learning cost → minimal (just instruct in natural language)

This is why the tool is made so that an AI agent can operate it through the same CLI and bundled documentation as a human.

### Sources are plain text in standard formats, and the tool only reads

The schema, data, views, and templates are all plain text in standard formats (JSON Schema / YAML / Markdown / Jinja2), owned by the user and managed in Git. There is no proprietary format.

The tool only reads them and generates; it offers no create, update, or delete (CUD) API. Reasons:

- A CRUD API over the structure of JSON Schema (`AppendAdditionalProperty` and the like) would be enormous to design
- With standard formats, users and AI agents already know how to write them and can edit the files directly
- Since the tool only reads, there is no need to write back (no round-trip preservation)

### Data model: a JSON tree with discipline

For the separation of data from views to hold, many different views must be assembled mechanically from one body of data. The assembling side (the query DSL, the templates) must be able to assume the shape of the data, so the data model needs discipline.

It is the same picture as a standard making many shapes possible (the studs of Lego bricks); the relational database is the strictest form of this discipline.

On the other hand, the sources are plain text in standard formats that users read and write directly. There, related data should sit together in one place, and giving a globally unique id to every child that has no natural key is a burden. So we allow the nesting that relational databases forbid. This is exactly the shape that YAML written by many hands accepts.

The data model the user defines is JSON with nesting allowed, with the following constraints added so that the query DSL and the templates can handle it easily:

- **Types are enforced** — every value has exactly one declared type. There is no untyped position, no position with more than one type, and no null (a missing value is an omitted key)
- **Attribute definitions are enforced** — an object has only the attributes that are declared. There is no object with arbitrary keys; the `{key: {...}}` way of listing keys is accepted only as a notation for a set of records, `[{id: key, ...}]`
