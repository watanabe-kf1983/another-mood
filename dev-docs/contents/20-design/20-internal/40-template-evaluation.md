# Template evaluation boundary

How the external design's [Trust Model](../10-external/70-trust-model.md) promise, "no arbitrary code runs from templates", is closed.

Since the promise is guarded by several modules and two tests sharing the work, the whole division is here, and each module's comment holds only its own share:

- `generator/template_engine.py` — the evaluator, and the boundary guard at the entrance to rendering
- `generator/inert.py` — the inert value model for data
- `generator/template_safe.py` — the enumeration of accepted helper return values
- `generator/data_tree.py` — nodes, and the `_`-prefixed metadata
- `generator/render_processor.py` — `render`, the only filter with a side effect
- `tests/components/generator/test_ssti.py` / `test_template_safe.py` — the engine's exposure rules, and the audit of the types' surfaces

Terms used in this chapter:

- **host capability** — a Python capability outside the template that reaches files, processes, the network, and the like
- **SSTI** — an attack that tries to reach a host capability through an expression planted in a template (server-side template injection)
- **inert value** — a value with no route to a host capability. A value that may be shown to a template
- **marshal** — the conversion that passes a Python value into the template's value model. Scalars are converted; objects are wrapped
- **finalize / `Markup` / subject** — terms of the external design's [Template](../10-external/50-template.md)
- **node** — a container with an address (anchor path). Two kinds, `MappingNode` / `ArrayNode`, of type `Node`. Narrower than the node of the external design's Template (a link target): it does not include prose headings. The value of a broken reference is `MissingNode` (the external design's [Template](../10-external/50-template.md))

## There is one evaluator

The only Jinja evaluator is `TemplateEngine` (`generator/template_engine.py`), and only the generator component (the `generate` and `reconcile` stages) holds one.

`generate` draws the author's templates and, in addition, the built-in templates (the cover, the database pages under `__db/`). `reconcile` draws only built-in templates (the failure page, the colophon, the warnings), and passes them only the `BuildReport` and build info. `site` only converts Markdown, and sees neither the author's templates nor the data tree.

What the external design depends on is that "every value that reaches a template passes the same boundary". Keeping one evaluator is the simplest way to keep that, and the number is not increased.

## Closed by the value model, not by a blocklist

Jinja2's SSTI routes (`__class__` to `__subclasses__()`, `attr('__class__')`, `map(attribute=)`, and so on) are not a collection of independent holes; they all grow from one value model, "touching Python objects by reflection".

So a runtime sandbox that forbids dangerous attributes one at a time, like Jinja2's `SandboxedEnvironment`, is not adopted. Filters that walk by attribute name, such as `attr` / `map(attribute=)`, are widely used in templates and cannot be forbidden.

What was adopted is an engine whose value model is structurally safe (minijinja, which holds values on the Rust side and has no dunders, the entrance to Python reflection), and on top of it the [marshal contract](#the-marshal-contract-values-that-reach-a-template-are-closed-to-inert-by-type-and-structure). The engine alone is not enough: the ordinary members of a Python object passed in are exposed, so the values passed in are closed by contract.

## DoS is not closed

The analysis behind the external design's [Trust Model](../10-external/70-trust-model.md#dos-is-not-closed-the-operator-fences-it-at-the-os-layer) ruling that "the tool holds no cap on time or memory":

- **A single bomb is refused structurally by minijinja.** It has a cap on the element count of `range(n)`, on template recursion, and on `*` repetition of strings and sequences, so a one-shot like `"x" * 10**12` does not pass
- **What remains is accumulation and amplification**, growing in bytes rather than in instructions. Doubling concatenation (`ns.x ~ ns.x` N times for 2^N bytes), filter amplification (`| indent(huge width)` turns a small input into a huge output with a scalar argument), nested loops over data sequences. Each step is of legal size; only the total explodes
- **minijinja's `fuel` does not close it.** `fuel` is a CPU budget counting one per instruction and does not see the bytes allocated, so the memory amplification above passes with a small instruction count. Switched on by default, it would look like a cap while stopping no memory, and hand out false reassurance
- **Time cannot be stopped on the tool's side either.** Evaluation runs inside a native extension, and control does not return to Python during a huge allocation or a long loop. Neither a timeout nor a signal on the tool's side reaches the middle of an evaluation
- **An OS-layer limit does close it.** `RLIMIT_AS` fails the allocation request itself, so the process in question is brought down deterministically rather than by thrashing or a random OOM kill. cgroups and containers bound time and CPU in the same place

The place to add `fuel`, should it be wanted, is `make_environment` (`generator/template_engine.py`).

## Premise: what minijinja exposes

What minijinja exposes to a template is the non-`_`, non-dunder members (attributes and methods) of the values passed in, and the elements of containers. The rules established by measurement:

- **dunders** (`__class__` and the like) are structurally sealed. Unreachable from dot notation, subscript, and the string attribute names of `attr` / `map(attribute=)` / `selectattr` / `groupby` alike
- **`_`-prefixed** attributes are undefined, and calling them as methods is an error. Whether the object derives from dict / list is irrelevant; it is purely the presence of `_`. This is what cuts the data tree's `_parent` / `_meta` off from templates and prevents walking out to raw Python objects
- **Non-`_` attributes and methods** are exposed and callable. Their return values can be walked further
- **globals** are not protected even under `_` names, and can be called by walking their members. So the only things the engine registers as globals are template helpers (filters live in a separate namespace and cannot be picked up as values)
- **The loader** is the only place a template chooses a path (`include` / `extends` / `import` / `render`), but it resolves neither `../` nor absolute paths, and stays within the template directory

Marshaling is asymmetric between convert and wrap. Scalars (str / int / float / bool / None and their subclasses) are converted to minijinja-native values, and their Python members do not cross over.

`pycompat` (the minijinja option that grows Python methods onto values; the external design's [Template](../10-external/50-template.md)) is also switched off, so strings have no `format` / `format_map`, and SSTI via `str.format`'s reflection does not work either.

Objects (including dict / list subclasses), on the other hand, are wrapped, and their Python methods leak. So the danger is confined to the route "reaching a non-`_` capability through a wrapped non-scalar".

`Markup` derives from str, so it is on the convert side: a template sees it as a plain string, and cannot reach Python members such as `__html__` / `unescape`.

It still reaches finalize as `Markup`. The engine's Python binding passes the original Python object to finalize, so the role of escape exemption is preserved (pinned by `TestMarkupExposure` in `test_ssti.py`).

These rules live on the engine's side and may change in a future version. So `tests/components/generator/test_ssti.py` fires the classic SSTI payloads at a real render and pins them.

What is pinned is both directions: the sealed side (the items above) and the exposed side the design assumes (calling non-`_` members, the unprotected globals). The exposed side turning red is not a breach but a sign that the engine has become stricter, meaning the contract might be relaxed.

## The marshal contract: values that reach a template are closed to inert by type and structure

The safety of an arbitrary Python object cannot be confirmed dynamically. `__getattr__`, instance attributes, and ABC registration can deceive introspection, so an audit by `dir()` is always a step behind.

So the contract is solved not as a runtime check but as a matter of keeping the discipline of the tool's own code by type and structure. The two exposed families are each closed:

- **Data**: the inert value model `InertValue = str | int | float | bool | None | InertMapping | InertArray` (`generator/inert.py`)
- The tree read from the upstream output (typed `object`) is validated and repacked by `ensure_inert` (parse, don't validate), and `MappingNode` / `ArrayNode` inherit the inert containers and add the address
- Inert containers are read-only after construction, and their mutators raise, because the data tree is shared by the drawing of every page and non-`_` methods are callable from templates
- **Helper (filter / global) return values**: the enumeration of what is accepted, owned by the engine, `TemplateSafe = InertValue | Node | Markup | MissingNode` (`generator/template_safe.py`)

The key points of the design:

- **The asymmetry: containers forbid subclassing, scalars are normalized.** Containers are wrapped and leak Python methods, so subclassing must not be able to add a capability. The only permitted subclasses are `MappingNode` / `ArrayNode`, which add the address
- Scalars in the data are converted and their members are unreachable, so there is no need to reject subclasses. Instead they are normalized to the exact types, so that the instances match the exact types the static type `InertValue` assumes. `Markup` is not data but a helper return value, accepted separately as `TemplateSafe`
- Containing subclasses is the static side's job. `ensure_inert` passes an already inert container through by `isinstance`, and there is no runtime check rejecting subclasses. It is kept by `@final` on `MappingNode` / `ArrayNode` and the discipline of inheriting the inert containers nowhere else
- **`TemplateSafe` is an enumeration, not a base type.** The acceptance requirement cannot be expressed by inheritance (a subclass could add a capability), so each concrete type is enumerated
- `TemplateSafe` is owned by the accepting side, and referenced only at the engine boundary (`template_engine`, and the generator that passes the helpers in). Producers only declare their own concrete return types (`Node | MissingNode` and the like), giving a one-way import from consumer to producer
- minijinja's undefined arrives as `None`, and helpers return `None` (there is no `Undefined` type in the enumeration)
- **Callables with side effects are forbidden as a rule.** The `render` filter is the one exception: it writes out a page. A template chooses only the subtemplate's name and the subject; the tool derives the destination from the subject's address, inside the output directory. Filters cannot be picked up as values (premise), so there is no route to the owning object either

## Enforcement layers

The contract secures three requirements:

- ① The data that reaches a template is inert
- ② No undeclared (foreign) attribute can be planted on a `TemplateSafe` type. If one could, it would be exposed as a non-`_` attribute and could carry a capability
- ③ A `TemplateSafe` type has neither non-`_` methods beyond its reference surface (a plain dict / list, the declared fields) nor protocol dunders. `__getattr__` / `__getitem__` / `__call__` fire even though a template cannot walk to them by name, because the engine or Python calls them itself as protocols

Per layer, the requirements it carries:

- **pyright (static)** — ① and ②. The typing of inert containers by `[InertValue]`, and the check of helper return types at the engine boundary
- **The render boundary guard (runtime)** — ①. The entrance to drawing (`_bind` in `template_engine.py`) binds the subject to `this`, and if the subject is a map, binds each of its keys too. Each binding is passed through `ensure_template_safe`, enforcing "only `TemplateSafe` reaches a template" at one point
- The boundary guard passes `Markup` and `MissingNode` through, sends data to `ensure_inert`, and raises on anything else. For uniformity, the drawing of the built-in templates (the cover, the database pages, the failure page, the colophon, the warnings) passes the same boundary
- **The surface-audit test** (`tests/components/generator/test_template_safe.py`) — ② and ③. Audits each `TemplateSafe` type across its whole MRO. The non-`_` surface must match the reference surface (for containers, a plain dict / list; for `MissingNode`, the declared fields with each value inert)
- The same test also checks that no foreign attribute can be planted (`__slots__` / frozen) and that there is no unexpected protocol dunder. `Markup` is on the convert side and its surface does not cross over, so it is out of scope (the SSTI regression test pins it)
- **The SSTI regression test** (`test_ssti.py`) — pins, on a real render, the engine-side exposure rules that the three layers above assume ([Premise](#premise-what-minijinja-exposes))
- **Residue** — removing `__slots__` and the like is caught by behavioral tests, but the deletion of the audit test itself is prevented by neither types nor tests, and falls to code review
