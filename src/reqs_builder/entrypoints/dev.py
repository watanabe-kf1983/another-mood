"""Dev command — build + watch for changes and rebuild, with Hugo live preview."""

from watchfiles import watch

from reqs_builder.adapters.renderer import render_dev
from reqs_builder.config import ProjectConfig
from reqs_builder.entrypoints.build import build


def dev(config: ProjectConfig) -> None:
    """Run build, start Hugo server, then watch and rebuild on changes."""
    assert config.contents_dir is not None

    if not config.contents_dir.exists():
        raise FileNotFoundError(f"contents directory not found: {config.contents_dir}")

    build(config)
    print("Build complete.", flush=True)

    hugo_process = render_dev(config)
    print(f"Hugo server started on http://localhost:{config.port}/", flush=True)

    try:
        for _changes in watch(config.contents_dir, debounce=300):
            build(config)
            print("Build complete.", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        hugo_process.terminate()
        hugo_process.wait()
