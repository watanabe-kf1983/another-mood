"""The watch-mode preview server's output handling."""

import socket
import threading
from pathlib import Path

import pytest

from another_mood.pipeline.site import HugoServerStartupError, SiteServeStage
from another_mood.pipeline.base import ComponentOutput


def test_startup_failure_carries_what_hugo_said(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        site = SiteServeStage(
            upstream=ComponentOutput(upstream),
            prep_dir=tmp_path / "prep",
            host="127.0.0.1",
            port=port,
        )

        with pytest.raises(HugoServerStartupError) as raised:
            with site.start_watching(threading.Event()):
                pass

    assert str(port) in raised.value.output
    assert raised.value.output in str(raised.value)
    assert capfd.readouterr().err == ""
