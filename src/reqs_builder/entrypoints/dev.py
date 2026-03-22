"""Dev command — build + watch for changes and rebuild, with Hugo live preview."""

from reqs_builder.adapters.renderer import render_dev
from reqs_builder.config import ProjectConfig
from reqs_builder.entrypoints.build import build
from reqs_builder.adapters.watcher import Watcher


def dev(config: ProjectConfig) -> None:
    """Run build, start Hugo server, then watch and rebuild on changes."""
    assert config.contents_dir is not None

    if not config.contents_dir.exists():
        raise FileNotFoundError(f"contents directory not found: {config.contents_dir}")

    build(config)
    print("Build complete.", flush=True)

    hugo_process = render_dev(config)
    print(f"Hugo server started on http://localhost:{config.port}/", flush=True)

    def rebuild() -> None:
        build(config)
        print("Build complete.", flush=True)

    try:
        Watcher([config.contents_dir], rebuild).run()
    except KeyboardInterrupt:
        pass
    finally:
        hugo_process.terminate()
        hugo_process.wait()
