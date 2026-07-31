from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from scripts.run_provider_console import ProviderConsoleHandler


@pytest.fixture
def provider_api():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderConsoleHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(url: str) -> dict:
    with urlopen(url, timeout=2) as response:  # noqa: S310 - loopback test server
        return json.load(response)


def _post(url: str, value: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(value).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=2) as response:  # noqa: S310 - loopback test server
        return json.load(response)


def test_health_and_stateful_command_round_trip(provider_api: str) -> None:
    assert _get(f"{provider_api}/api/v1/health") == {
        "mode": "synthetic-local",
        "status": "ok",
    }
    session = _post(f"{provider_api}/api/v1/provider-sessions", {})
    assert session["stage"] == "intake"
    assert session["version"] == 1

    updated = _post(
        f"{provider_api}/api/v1/provider-sessions/{session['session_id']}/commands",
        {"command": "compile_referral", "expected_version": 1},
    )
    assert updated["stage"] == "review_draft"
    assert updated["version"] == 2
    assert updated["metrics"]["fields_prefilled"] == 8

    fetched = _get(
        f"{provider_api}/api/v1/provider-sessions/{session['session_id']}"
    )
    assert fetched == updated


def test_static_console_is_served_by_same_origin(provider_api: str) -> None:
    with urlopen(  # noqa: S310 - loopback test server
        f"{provider_api}/network.html", timeout=2
    ) as response:
        html = response.read().decode("utf-8")
    assert "<title>Provider operations · CareTrust</title>" in html
    assert 'id="workflow-panel"' in html
