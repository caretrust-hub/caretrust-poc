"""Serve the operational provider console and its synthetic workflow API."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from caretrust.provider_operations import ProviderWorkflow, WorkflowConflict


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


class ProviderConsoleHandler(SimpleHTTPRequestHandler):
    workflow = ProviderWorkflow()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(DEMO), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/v1/health":
            self._json({"status": "ok", "mode": "synthetic-local"})
            return
        if path.startswith("/api/v1/provider-sessions/"):
            session_id = path.removeprefix("/api/v1/provider-sessions/")
            try:
                self._json(
                    self.workflow.get(session_id).model_dump(mode="json")
                )
            except KeyError as exc:
                self._problem(HTTPStatus.NOT_FOUND, str(exc))
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/v1/provider-sessions":
                session = self.workflow.create_demo_session()
            elif path.startswith("/api/v1/provider-sessions/") and path.endswith(
                "/commands"
            ):
                session_id = path.removeprefix(
                    "/api/v1/provider-sessions/"
                ).removesuffix("/commands")
                session = self._command(session_id, payload)
            else:
                self._problem(HTTPStatus.NOT_FOUND, "unknown endpoint")
                return
            self._json(session.model_dump(mode="json"), HTTPStatus.CREATED)
        except (KeyError, WorkflowConflict, ValueError) as exc:
            self._problem(HTTPStatus.CONFLICT, str(exc))
        except json.JSONDecodeError:
            self._problem(HTTPStatus.BAD_REQUEST, "request body must be JSON")

    def _command(self, session_id: str, payload: dict[str, Any]):
        command = payload.get("command")
        expected_version = payload.get("expected_version")
        if command == "compile_referral":
            return self.workflow.compile_referral(
                session_id, expected_version=expected_version
            )
        if command == "review_draft":
            return self.workflow.review_draft(
                session_id,
                reviewer_ref=payload.get("reviewer_ref", "user:demo-coordinator"),
                corrections=payload.get("corrections", {}),
                resolved_items=payload.get("resolved_items", {}),
                expected_version=expected_version,
            )
        if command == "record_patient_approval":
            return self.workflow.record_patient_approval(
                session_id,
                patient_ref=payload.get("patient_ref", "patient:synthetic-malia"),
                approved=bool(payload.get("approved")),
                expected_version=expected_version,
            )
        if command == "assign_worker":
            return self.workflow.assign_worker(
                session_id,
                worker_id=str(payload.get("worker_id", "")),
                supervisor_ref=payload.get(
                    "supervisor_ref", "user:demo-supervisor"
                ),
                expected_version=expected_version,
            )
        if command == "request_app_access":
            return self.workflow.request_app_access(
                session_id,
                app_id=str(payload.get("app_id", "")),
                expected_version=expected_version,
            )
        if command == "revoke_assignment":
            return self.workflow.revoke_assignment(
                session_id,
                actor_ref=payload.get("actor_ref", "user:demo-supervisor"),
                reason=str(payload.get("reason", "")),
                expected_version=expected_version,
            )
        raise ValueError(f"unknown command: {command!r}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _json(
        self, value: object, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(value, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _problem(self, status: HTTPStatus, detail: str) -> None:
        self._json(
            {
                "type": "about:blank",
                "title": status.phrase,
                "status": status.value,
                "detail": detail,
            },
            status,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ProviderConsoleHandler)
    print(f"CareTrust provider console: http://{args.host}:{args.port}/network.html")
    print("Synthetic data only. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
