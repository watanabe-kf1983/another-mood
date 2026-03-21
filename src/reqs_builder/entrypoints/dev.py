"""Dev command — build + watch for changes and rebuild."""

from watchfiles import watch

from reqs_builder.config import ProjectPaths
from reqs_builder.entrypoints.build import build


def dev(paths: ProjectPaths) -> None:
    """Run build, then watch contents_dir and rebuild on changes."""
    assert paths.contents_dir is not None

    if not paths.contents_dir.exists():
        raise FileNotFoundError(f"contents directory not found: {paths.contents_dir}")

    print(f"Watching {paths.contents_dir} for changes...", flush=True)

    build(paths)
    print("Build complete.", flush=True)

    try:
        for _changes in watch(paths.contents_dir, debounce=300):
            build(paths)
            print("Build complete.", flush=True)
    except KeyboardInterrupt:
        pass
