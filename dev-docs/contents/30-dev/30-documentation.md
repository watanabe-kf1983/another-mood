# Writing Documentation

The readers of each location, and the conventions for what to write and what not to. Notation that crosses locations (paragraph length, the product name, the self-definition) is here too. The table of the source of truth per kind of information is in the "Documentation" section of `DEVELOPMENT.md`.

## Families

Documentation is managed in four families. The three families under `dev-docs/` are managed with Another Mood itself:

| Family | Content | Readers |
|---|---|---|
| `docs/` | User documentation. Implemented features only | Users (humans and LLMs) |
| `dev-docs/concept/` | The product concept (the vision, the core design decisions). The grounds for development decisions | Developers |
| `dev-docs/design/` | The design. Part 1 is the external design (of the user-visible behavior, what we keep on purpose); part 2 is the internal structure (the arrangement of layers and stages, and the promises that keep it) | Developers |
| `dev-docs/dev/` | The development conventions and procedures opened for a particular occasion (environment / dependencies / documentation / release). Written concisely and prescriptively. The conventions every change needs, and the pointers here, are in `DEVELOPMENT.md` | Developers |

## Paragraph length

A paragraph is at most 380 characters (counted as visible characters excluding link URLs; each list item counts as a paragraph). This applies to every document: the four families plus `README.md` and `DEVELOPMENT.md`. If a paragraph runs over, split it at a sentence boundary, or turn parallel items into a list. Long paragraphs get skipped.

The limit was set when these documents were written in Japanese, at 200 characters, and converted by the ratio of average sentence length (English is about 1.9 times). `make ci` checks it.

## The product name and the self-definition

The notation conventions for how the product is called and how it describes itself. They apply not only to documentation but to every place a person reads as text, such as docstrings and `--help`.

### How the tool's name is written

| Layer | Notation |
|---|---|
| Prose (README / docs / dev-docs / docstrings / --help / commit messages, etc.) | `Another Mood` |
| Technical identifiers (paths, URLs, the PyPI / GitHub repository name, the project root) | `another-mood` |
| Python package and modules | `another_mood` |
| CLI command | `mood` |

The hyphenated spelling (`another-mood`) is unnatural in English prose, so prose uses the title-case `Another Mood`. Technical identifiers (URLs, paths, package names) stay `another-mood` because of GitHub / PyPI / language constraints.

The criterion is **usage, not file format**: a docstring in code or `--help` output that a human reads as English text counts as prose.

### How to write the self-definition (tagline / description)

The tool's self-definition has two layers, written separately and never mixed:

- **Means (universal, fixed)**: a processor of source-based databases — the essence of the implementation
- **Effect (the value actually delivered now)**: what it actually delivers at present

The rules for writing them apart:

- The tagline in the pyproject.toml description, `mood --help`, the opening of the README, and the like is written as **Means + current Effect**
  - Example: `A processor of source-based databases, keeping related documents in sync.`
- The Effect side **never hints at future extension** (no "and other ..." and the like). Honesty comes first
- On the other hand, avoid pinning the Vision down as an Effect ("documentation build tool" narrows the reading of the Means, so it is out)
- The Vision in product.md is managed separately as the abstraction of the Effect layer. The tagline and the Vision may drift apart over time

## `docs/`

Follows [Diátaxis](https://diataxis.fr/): `reference/` is written as reference, `guides.md` as tutorial / how-to / explanation. Plain Markdown.

Both human readability and the behavior of an LLM that has read it bear directly on the UX, so there is no compromise on quality. What is written is also treated as the source of truth of the external specification (the contract with users), but that is a consequence, not the purpose of writing.

Only the promise layer is written in `reference/`. Precise rules outside the user's concern are not written (the code and the fixture tests hold them), keeping the reference to a size a user can read.

## `dev-docs/design/`

The design is written to be read before starting work. It has done its job if the reader learns what must not be broken, what is where and how it connects, and can decide which code or source of truth to open next. The more there is to read, the less it is read before work, so what goes in is kept narrow.

The design has two parts:

- **Part 1: External Design** — of the user-visible behavior, what we keep on purpose without making it a contract, and why. The chapters follow the same units as `docs/reference/`. The exception is the trust boundary (Trust Model), which has no page corresponding to a contract but is a boundary visible to the user, so it is a chapter of its own
- **Part 2: Internal Structure** — the arrangement of layers and stages, and the promises that keep it. The description of the arrangement exists only here

### External design

- Limited to what could have been chosen differently and might be changed in good faith (example: duplicate keys are errors, not last-wins)
- Written in the chapter that covers the behavior, wherever it is implemented. So that breaking it is noticed, the test that guards it names the heading (the test convention in `DEVELOPMENT.md`)
- What is in `docs/reference/` as a contract is not restated

It is rewritten only when the behavior itself changes. Rebuilding the implementation needs no rewrite, so it ages slowly.

### Internal structure

- **Pointers** — what each layer and stage is responsible for, what passes between stages, and what is shared. The shared vocabulary is defined here too. The content is not restated; point at the code path or the source of truth
- **Promises that keep the arrangement** — invariants whose breaking would make the arrangement written here diverge from reality. Written next to the part of the arrangement they keep (example: next to "stages are connected through files", "components do not import each other")
- **Promises kept across layers or stages** — even if not keeping the arrangement, an invariant that several layers or stages keep together goes here (example: no stage rewrites its own output)

In both parts, the one sentence of intent is written in the same place as its object, and not indexed in a separate system (ADRs and the like). In the same place, the intent is seen when the object changes, and missed updates are rarer.

### What does not go here

| Content | Where it goes |
|---|---|
| Mechanism (how one layer or stage does it, inside) | The code |
| A decision for implementation reasons, closed within one layer or stage | A comment at the place where a change that breaks it would be made |
| A contract (behavior the user may rely on) | `docs/reference/` |
| Product policy | `dev-docs/concept/` |
| Promises about how development proceeds | `dev-docs/dev/` |
| History (comparative surveys, rejected options) | The PR body (which survives as the squash commit body on main) |

### Telling the boundaries

- **Pointer or mechanism** — is it between layers and stages, or inside one layer or stage? Between, it is a pointer and goes in the internal structure; inside, it is a mechanism and is left to the code (example: that a stage reads the preceding stage's output directory is a pointer; how the JSON is written into that directory is a mechanism)
- **Where a decision goes** — if the reason lies in user-visible behavior, the external design. If the reason lies in the implementation, the internal structure when it crosses layers or stages, and a comment where the change that breaks it would be made when it is closed within one. If it is a promise about how development proceeds rather than about the code, `dev-docs/dev/`

## Updating the indexes

When a document is added, removed, or moved, check and update the links from the following indexes before opening a pull request:

- The `index.md` of each dev-docs folder (`dev-docs/contents/**/index.md`) — the list of chapters. The overall table of contents is built, so it is not edited by hand
- `docs/index.md` — the user-facing top
- `docs/catalog.yaml` — the catalog of the documentation that `mood docs` serves
- `DEVELOPMENT.md` — the pointers for developers
