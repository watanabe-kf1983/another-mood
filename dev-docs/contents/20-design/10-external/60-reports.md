# Reports

Behavior kept on purpose, outside the contract of `docs/reference/reports.md`. Of the output tree, the content of `__db/` is covered by [View](40-view.md#database-pages), and the values on `__build_info/` by [Template](50-template.md#build_info). What is covered here is the cover and the placement of those pages.

Terms used in this chapter:

- **report** — one set of output the user's templates draw from the data. Configured by `definition/reports.yaml` (`docs/reference/reports.md`)
- **edition** — an output of the same report in a different form. The differences are `file_per` (which types of node go into separate files) and `vars` (values the templates read back) (Editions, same document)
- **form A / form B** — the two ways of writing `reports.yaml`. Form A writes an edition's settings at the top level and becomes one edition named `default`. Form B writes several by name under `editions:` (Editions, same document)
- **database pages** — the pages under `__db/` that the tool draws automatically from the schema and view definitions ([View](40-view.md#database-pages)). Drawn by the same mechanism as an edition. In the cover's section name, Database Information
- **mount** — a directory directly under the output root given to an edition or to system-generated output. `{edition}/`, `__db/`, and so on
- **node / anchor path / subject / blob / build info / colophon** — terms of [Template](50-template.md). The subject of a split page determines that page
- **cover** — the `index.md` at the output root. The entry to the Reports and the database pages. Ends with link sections to the colophon and the warnings
- **diagnostics** — reports of problems pointing at a source file and line. There are warnings, which let the build continue, and errors, which stop it
- **warnings page** — the page `__warnings/` listing the warnings. Created only when there are warnings. `--strict` fails the build on warnings too (`--strict` in `docs/reference/cli.md`)
- **build failure page** — the `index.md` placed instead of the cover when an error stops the build. Lists the diagnostics and the errors that cannot point at a source

## edition

### An edition is the same report in a different form, not a profile chosen per environment

Every declared edition is generated in one build and placed side by side under `{outDir}/{edition}/`. The intended use is to split pages finely for the web and bind them into one file for print. Wanting both at once is the usual case, so there is no need for a way to pick one.

There is no option like `--edition` to pick one at build time. Nor is it an axis for differences in renderer or format: the conversion from Markdown to HTML is the same for every edition. The contract's "side by side" means the artifacts sit next to each other, not that they run in parallel.

## Output paths

### A file name is the anchor path percent-decoded per segment, with only the characters a file system cannot hold escaped as `~XX`

A split page's path is derived from the subject's anchor path (Output path in the contract), but the address string is not used as the file name as is. It is percent-decoded segment by segment, because browsers, static servers, GitHub, and Hugo all decode the URL before looking for the file.

Decoding per segment keeps a `%2F` inside an id from turning into a separator. A `/` that appears on decoding becomes `~2F` by the next rule.

Of the characters that appear on decoding, only those a file system cannot hold (the Windows reserved characters including `/`, `~` itself, a trailing `.` or space) are escaped as `~XX`.

Not `%XX`, because Hugo takes `%XX` in a file name as already URL-encoded and preserves it. Servers decode the URL before looking for the file, so a file with `%XX` in its name is reachable from no URL.

Link URLs are also made from this file name (`href` percent-encodes the page path), so a `~XX` file is reached by a `~XX` URL. The anchor path appears in a URL only in the fragment.

The output location of blobs (copied into `blob/` directly under each edition's root; [internal structure](../20-internal/30-communication/index.md#a-blobs-anchor-path-is-also-its-output-address)) and the edition directory names get their names by the same rule. Problems that cannot be squashed per character (exceeding the path length, Windows device names) are handled separately by the writing side, not by escaping (`shared/windows_reserved_name.py`).

### Each edition and each mount is a self-contained subtree of relative links

The layout of the output root:

```
{outDir}/
  index.md          ← cover: project name, Reports, Database Information
  default/          ← the user's edition (web/, print/, etc. with form B)
  __db/             ← database pages
  __build_info/     ← colophon
  __warnings/       ← warnings (only when there are any)
```

Link URLs are page-relative, so the mount prefixes `{edition}/` and `__db/` do not appear in links. Each edition can be carried off and placed elsewhere on its own without breaking, and mounts are transparent to link resolution.

The cover is not an edition; it is a thin page drawn once. `__db/` is drawn by the edition mechanism, but it is not a report in a different form, so on the cover it is placed in a separate entry rather than listed among the Reports.

## The cover and the diagnostic pages

### The colophon is a separate page, and the cover carries only a link section

The colophon is the separate page `__build_info/` listing all of the build info, and the cover links to it only through a `## Build Information` link section. The same form as the warnings page.

The file boundary is separated so that the user can leave it out of what they publish.

The colophon speaks of the facts of the build environment (values the operator injected, the absolute path of the project), and for a user publishing the output, the reader is no longer "the person who built it". Mixed into the cover there is no way to remove it, but as a separate directory, excluding the one `__build_info/` suffices.

For a user who commits the build result, the cover also stops being dirtied by a timestamp that moves every time. A timestamp that does not move is meaningless, so the colophon producing a diff is itself by design.

The cover's link section carries no values. Putting a summary there would make the tool the judge of "which keys deserve the cover". The colophon is the page that lists everything without choosing, and not having that judgment is its position.

### The tool is not given a mechanism for excluding things from publication

What to publish is the job of the deployment tool (rsync, `aws s3 sync`, CI). Once the tool starts carrying publication-policy flags, requests of the same kind pile up. All the tool takes on is "what you may want to leave out is gathered in one place", and `__warnings/` stands in the same position.

### Only the build failure page embeds the colophon

When an error stops the build, the cover is replaced by the failure page, and pages drawn partway are not kept. Neither `__db/` nor the warnings page is created; the warnings are listed among the failure page's diagnostics. The failure page embeds the colophon as a table rather than linking to it.

Whoever reads the failure page is always the person who built it, and no user publishes a failed output. It is also a page where the diagnostics have already baked in absolute paths, so the reason for separating the colophon does not hold. As the only page the reader sees on failure, it is also the only place the colophon can reach.
