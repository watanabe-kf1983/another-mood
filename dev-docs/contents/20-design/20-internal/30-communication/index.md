# Inter-Stage Communication

The overview of the hand-over between stages ([Architecture](../10-architecture.md#how-build-and-watch-are-served-by-the-same-components)). It covers how output directories are carried downstream (transport), how failures are conveyed downstream (error propagation), and what is passed by argument rather than through files (build info).

The shape of the data that flows is in [JSON data model](10-json-data-model.md); the inventory built from the schema and shared by every stage is in [Data catalog](20-data-catalog.md).

## Transport

The workspace is the working directory in which the stages' output directories sit side by side for one run (`tmp_dir` in the user's settings, `Workspace.root` in code). The Output column of the [stage table](../20-pipeline.md#stages) is its content. Below is how directories are carried within the workspace, and which invariants are kept.

### Hand-over between stages is by hardlink

Hand-over between and within stages is by **hardlink**, not by copying files. Hand-over is done by mirroring directories, so carrying by copy would duplicate each file as many times as there are hops. The real bytes are copied once, at the contents → workspace boundary, and every later hop shares the same inode.

Where a hardlink cannot be made (across file systems, or on a file system without support, such as an exFAT external drive or an SMB share), it falls back to copying automatically, so that the [product's supported platforms](../../../10-concept/10-product.md#what) (Linux / macOS / Windows) are not narrowed (`transfer.link_or_copy`).

### Hence every stage is write-once

A hardlink shares the inode, so if any stage wrote in place into an existing file, every directory holding the same inode (including published output) would be overwritten straight through, and no watcher event would fire for it.

So **every stage is write-once**: it must not write into an existing file in the workspace, and replacement is always unlink → recreate. This constraint is what makes hardlink transport safe.

The components that make up the stages and the adapters (Hugo preparation and so on) are both under this constraint, and the real pipeline is run twice to check every stage (`tests/pipeline/test_write_once_sweep.py`).

The files in `contents/` are outside this constraint, so at the boundary they are really copied, not hardlinked. For blobs, even this boundary copy is replaced by a hardlink from the previous output when size + mtime match (`_mirror_blob_bytes` / `_reuse_unchanged` in `content_normalizer.py`).

### Scope and preconditions

- **Every file** is hardlinked, not blobs alone. Holding a blob-detecting predicate per tree root would turn any misjudgment straight into an inode-sharing accident, so it was simplified to the single rule "every file write-once".
- So that `os.link` succeeds, each stage's temp is placed on the same file system as its output (`mkdtemp` in `dir_lock`).

### A blob's anchor path is also its output address

A blob node's anchor path `/blob/<id>` is mirrored as an output path directly under each edition's output root (the conversion from address to file name is in [Reports](../../10-external/60-reports.md)). Link resolution (where href points) and blob placement are both done by `generate`, and `publish` ([stage table](../20-pipeline.md#stages)) only copies reconcile/ as it is, so they agree on one address and never drift.

### Output directories are updated atomically

Per directory, each stage's output directory is updated atomically, and no intermediate state is visible downstream (the invariant [Architecture](../10-architecture.md#how-build-and-watch-are-served-by-the-same-components) assumes). Implemented by `dir_lock`'s `exclusive_write` (write to temp, then sync into the output under the lock) and `exclusive_read` (take a point-in-time copy of the upstream under the lock).

The details of the implementation and its rationale are in the module docstrings of `transfer.py` / `dir_lock.py`.

## Error propagation: BuildReport

The `BuildReport` that the components' shared foundation makes from an exception ([Architecture](../10-architecture.md#how-build-and-watch-are-served-by-the-same-components)) is placed as `__build_report.json` in `reports/` in each stage's output directory, next to the artifacts in `data/` (the key name is a reservation of [JSON data model](10-json-data-model.md#reserved-prefixes)). Errors that stop the build and warnings that let it continue ride on the same report, each with a `severity`.

A downstream stage collects the upstream `reports/` before running its body, and if there was a failure, skips the body and carries only the reports over into its own `reports/`.

## Build info travels outside the data flow

The facts of one run (the processor, the injected values, the manifest) are assembled by `Workspace`'s `build_info` (`pipeline/workspace.py`; flattening nested values into dot-separated keys is `components/shared/build_info.py`).

It is passed by argument to `generate` (the template's `build_info` function) and `reconcile` (the colophon page and the failure page), and does not enter `compose`'s output.

A failed stage emits no artifacts and passes only the `BuildReport` downstream, so if build info flowed as data from an upstream stage, it would not reach `reconcile` when upstream failed, and the colophon could not be shown on the failure page. The user-visible reason (not making a view's output depend on the machine) is in [Template](../../10-external/50-template.md#build-info-is-read-only-by-templates-and-does-not-flow-into-the-data-layer).
