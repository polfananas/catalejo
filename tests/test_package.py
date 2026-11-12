import json
from pathlib import Path

import catalejo


def test_version_is_exposed() -> None:
    assert catalejo.__version__


def test_server_json_matches_package_version() -> None:
    # The MCP registry rejects a server.json whose version isn't on PyPI yet,
    # so it has to move together with __version__.
    server = json.loads((Path(__file__).parents[1] / "server.json").read_text())

    assert server["version"] == catalejo.__version__
    assert {p["version"] for p in server["packages"]} == {catalejo.__version__}
