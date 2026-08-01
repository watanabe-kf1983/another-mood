"""Tap — assemble the composed namespace into one JSON document."""

from pathlib import Path

from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model, save_model

TAP_DOCUMENT_NAME = "tap.json"


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def tap(data_dir: Path, *, out_dir: Path) -> None:
    """Merge a stage's output into one document holding its top-level namespace."""
    save_model(out_dir / TAP_DOCUMENT_NAME, load_model(data_dir))
