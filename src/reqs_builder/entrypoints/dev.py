"""Dev command — build + watch for changes and rebuild, with Hugo live preview."""

from watchfiles import watch

from reqs_builder.adapters.renderer import render_dev
from reqs_builder.config import ProjectPaths
from reqs_builder.entrypoints.build import build


def dev(paths: ProjectPaths, port: int = 1313) -> None:
    """Run build, start Hugo server, then watch and rebuild on changes."""
    assert paths.contents_dir is not None

    if not paths.contents_dir.exists():
        raise FileNotFoundError(f"contents directory not found: {paths.contents_dir}")

    build(paths)
    print("Build complete.", flush=True)

    hugo_process = render_dev(paths, port)
    print(f"Hugo server started on http://localhost:{port}/", flush=True)

    try:
        for _changes in watch(paths.contents_dir, debounce=300):
            build(paths)
            print("Build complete.", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        hugo_process.terminate()
        hugo_process.wait()
