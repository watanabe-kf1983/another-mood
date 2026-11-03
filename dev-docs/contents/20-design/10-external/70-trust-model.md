# Trust Model

The boundary between who wrote a template and on whose machine it runs. The only chapter with no corresponding page in `docs/reference/`. `build` / `watch` evaluate the project's templates, so this boundary decides the product's safety.

Only the behavior we keep and its reasons are here. How it is closed (the engine's exposure rules, the marshal contract, the enforcement layers) is in [Template evaluation boundary](../20-internal/40-template-evaluation.md) of the internal structure.

Terms used in this chapter:

- **author / operator** — [Role terms](../index.md#role-terms). The subject of this chapter is that the two are not necessarily the same
- **RCE** — calling, from a template, Python capabilities that reach outside the tool (files, processes, the network) and running arbitrary code. The internal structure sees it as the route of injection through templates and calls it SSTI
- **running-text escape** — escaping the Markdown syntax characters of a value emitted by `{{ }}` just before output (Markdown escaping in `docs/reference/template.md`)
- **prose** — a Markdown file in `contents/`. Its body goes to the output as is ([Schema](30-schema.md#prose))

### Building a third party's project runs no arbitrary code from its templates

Projects can be distributed. Running `mood build` locally on a project someone else wrote never runs code planted in its templates on the operator's machine. All a template can do is shape the data it is given into a string with filters and functions; it reaches neither files nor processes nor the network.

With `make`, `npm install`, or Jekyll, building means running the code the project carries, and an untrusted project must not be built. This tool is not like that: templates can be treated as content as safe as data.

This is kept not by "forbidding dangerous constructs one by one" but by "the values visible from a template having no way out in the first place". A list of prohibitions is broken with every omission; with no way out, there is no omission. How the way out is blocked is in [Template evaluation boundary](../20-internal/40-template-evaluation.md) of the internal structure.

#### docs carries neither a guarantee nor a danger notice

What `docs/` promises is how to use the tool; it makes no safety guarantee. Placed in the contract as a guarantee, a change of premise in a future version of the engine would break the contract. Here it is held as behavior kept on purpose.

Nor is the opposite notice, "do not build untrusted projects", placed. With RCE closed, it would be an over-warning. The only attack surface left in execution is DoS, and that is closed by the operator, not the tool (below). Whether a reader trusts the raw HTML an author wrote is a matter of trust in the output, and does not count as attack surface ([raw HTML](#raw-html-is-a-matter-of-the-authors-expressiveness-a-separate-layer-from-execution-safety)).

### The only place code can run is a template

Of a project's sources, the only one "evaluated" during a build, that is, that can execute anything at the writer's direction, is `definition/templates/`. The other sources are only read and execute nothing:

- **`contents/`** — data and prose. Read as values only, never evaluated. On the way to the output, data values pass the running-text escape and prose passes as Markdown body
- **`definition/schema.yaml`** — declarative type definitions
- **`definition/views/`** — the declarative query DSL. No `eval`, no expression language
- **`definition/reports.yaml` / `sbdb.yaml` (the project's manifest)** — declarative settings

The step that turns the generated Markdown into HTML (Hugo) only converts Markdown. The layouts Hugo interprets are built in, and a project can add neither layouts nor shortcodes.

So the defense may be concentrated at the one point of template evaluation. That there is only one evaluator is kept by [Template evaluation boundary](../20-internal/40-template-evaluation.md#there-is-one-evaluator).

### The only outside values that reach a template are those the operator hands over explicitly

What a template can read from outside the project is only the values of `build_info` (what goes on the colophon) ([Template](50-template.md#build_info)). Of those, what the operator can put in is `vars.*`, passed one by one, by name, through `--var` and `MOOD_VARS_*` (Injected values in `docs/reference/cli.md`).

A namespace such as `env.*` for reading environment variables directly is not created. If templates became readers of the environment, values the operator never meant to pass, such as CI credentials, could be baked into the output.

This is the inbound counterpart of "the values visible from a template have no way out" above. It opens no hole in the policy of closing the set of values that reach a template ([Template evaluation boundary](../20-internal/40-template-evaluation.md#closed-by-the-value-model-not-by-a-blocklist)).

What is closed is the set of keys. The only route by which the operator can deliver a value under an arbitrary name is `vars.*`; the keys of the processor and the facts of the run (`processor.*`) and of the manifest (`manifest.*`) are decided by the tool and the sources.

The values of `processor.config.*` also change with config environment variables such as `MOOD_OUT_DIR`, but that is a copy of the actual startup, and the keys are fixed by the config's type.

### DoS is not closed; the operator fences it at the OS layer

A template can exhaust time or memory. The tool does not stop this, and has no option for capping a build's time or memory.

The only layer that can reliably bound memory is the OS (cgroups, containers, `RLIMIT_AS`); a cap inside the tool does not stop memory, and only hands out false reassurance for looking like a cap. Time is bounded at the same layer.

Evaluation runs inside a native extension and cannot be interrupted by a timeout on the tool's side (the analysis is in [Template evaluation boundary](../20-internal/40-template-evaluation.md#dos-is-not-closed) of the internal structure).

The axis of the distinction is whether the operator trusts the project. Building a project you wrote, or chose and trust, on your own machine, the only one hurt by a runaway is you, and that is accepted.

The moment an untrusted project (a third party's distribution) runs on build infrastructure, the operator fences the process at the OS layer. On CI and build infrastructure, fencing processes that way is the normal practice anyway.

### Raw HTML is a matter of the author's expressiveness, a separate layer from execution safety

Converting the generated Markdown to HTML lets raw HTML through (Hugo's setting `unsafe = true`). It is needed to embed the link landing spots `<a id>` ([Template](50-template.md#a-heading-has-only-an-address-within-its-record-and-no-a-id-is-stamped)) in Markdown as raw HTML.

Hugo's default `unsafe = false` is a defense for rendering untrusted Markdown, a different premise from this tool, which renders a project the author owns.

The exposure is narrow. Data values pass the running-text escape, and the content of code spans and fenced blocks is always HTML-escaped by Hugo's Markdown processor. What newly passes is only the author's own templates, prose, and `| safe`, and since the author already has full power over the sources and templates, it is no escalation.

Even when author ≠ operator, the remaining difference is "does a third party trust the output the author wrote in raw HTML", a matter of trust in the output, handled independently of execution safety.

Sealing off RCE is the execution-safety problem of "templates not reaching code outside the tool"; raw HTML is the expressiveness problem of "the author answering for their own output".
