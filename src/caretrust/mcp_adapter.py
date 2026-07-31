"""Dependency-free, read-only MCP stdio/JSON-RPC adapter for CareTrust.

The adapter is deliberately a thin boundary over existing deterministic POC
services.  It does not retain canonical case state, evaluate a new authority
path, issue tokens, or expose source packets.  Every call builds the existing
synthetic case afresh and returns an allowlisted projection, draft, validation,
explanation, or explicitly non-authoritative simulation.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from typing import Any, Callable

from caretrust.app_onboarding import (
    ApplicationOnboardingCompiler,
    make_application_description,
)
from caretrust.case_bundle import (
    build_synthetic_case_bundle,
    canonical_sha256,
    evaluate_case_permission,
    validate_case_bundle,
)
from caretrust.compiler import CompilerService, make_intent_statement


JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-11-25"
_SERVER_NAME = "caretrust-local-mcp"
_SERVER_VERSION = "0.4.0"
_RAW_FIELD_NAMES = frozenset((
    "uploaded_document",
    "uploaded_extraction_draft",
    "ocr_text",
    "raw_packet",
    "clinical_holder_revocation_deny",
))


class ToolInputError(ValueError):
    """A fail-closed tool input error returned in the MCP tool result."""


def _schema(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "caretrust_draft_delegation",
        "description": "Compile synthetic patient language into an evidence-linked, non-activatable delegation draft.",
        "inputSchema": _schema(
            {
                "intent_id": {"type": "string", "minLength": 1},
                "patient_ref": {"type": "string", "minLength": 1},
                "utterance": {"type": "string", "minLength": 1, "maxLength": 4000},
                "created_at": {"type": "string", "format": "date-time"},
            },
            ("intent_id", "patient_ref", "utterance", "created_at"),
        ),
    },
    {
        "name": "caretrust_propose_app_profile",
        "description": "Compile synthetic application material into a reviewable RAR/profile and minimum-data proposal; never registration.",
        "inputSchema": _schema(
            {
                "application_id": {"type": "string", "minLength": 1},
                "source_id": {"type": "string", "minLength": 1},
                "description": {"type": "string", "minLength": 1, "maxLength": 8000},
                "openapi": {"type": "object"},
                "created_at": {"type": "string", "format": "date-time"},
            },
            ("application_id", "source_id", "description", "created_at"),
        ),
    },
    {
        "name": "caretrust_list_case_permissions",
        "description": "Read the minimum-data permission projection for the fixed synthetic case, optionally for one caregiver.",
        "inputSchema": _schema({"caregiver_ref": {"type": "string", "minLength": 1}}),
    },
    {
        "name": "caretrust_explain_decision",
        "description": "Explain one canonical case decision using policy/reason and minimum-data receipt fields only.",
        "inputSchema": _schema({"decision_id": {"type": "string", "minLength": 1}}, ("decision_id",)),
    },
    {
        "name": "caretrust_validate_case",
        "description": "Run the existing synthetic-case contract/linkage validator; this is not external conformance certification.",
        "inputSchema": _schema({}),
    },
    {
        "name": "caretrust_simulate_access",
        "description": "Re-run existing deterministic case policy for one canonical request without creating a token, receipt, or disclosure.",
        "inputSchema": _schema(
            {
                "request_id": {"type": "string", "minLength": 1},
                "as_of": {"type": "string", "format": "date-time"},
            },
            ("request_id",),
        ),
    },
    {
        "name": "caretrust_project_standards",
        "description": "Read published standards projection metadata and stated semantic/non-claim boundaries for the synthetic case.",
        "inputSchema": _schema({"canonical_id": {"type": "string", "minLength": 1}}),
    },
)
_TOOLS_BY_NAME = {item["name"]: item for item in TOOL_DEFINITIONS}


def _error(code: int, message: str, request_id: Any = None, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}
    if data is not None:
        error["error"]["data"] = data
    return error


def _tool_result(value: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, sort_keys=True, separators=(",", ":"))}],
        "structuredContent": value,
        "isError": is_error,
    }


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ToolInputError(f"{field} must be an RFC 3339 date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolInputError(f"{field} must be an RFC 3339 date-time string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ToolInputError(f"{field} must include a timezone offset")
    return parsed.astimezone(UTC)


def _validate_args(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolInputError("arguments must be an object")
    schema = _TOOLS_BY_NAME[name]["inputSchema"]
    properties = schema["properties"]
    unknown = set(arguments) - set(properties)
    if unknown:
        raise ToolInputError(f"unknown tool argument(s): {', '.join(sorted(unknown))}")
    missing = set(schema["required"]) - set(arguments)
    if missing:
        raise ToolInputError(f"missing required tool argument(s): {', '.join(sorted(missing))}")
    checked = deepcopy(arguments)
    for key, definition in properties.items():
        if key not in checked:
            continue
        value = checked[key]
        if definition["type"] == "string":
            if not isinstance(value, str) or not value:
                raise ToolInputError(f"{key} must be a non-empty string")
            if "maxLength" in definition and len(value) > definition["maxLength"]:
                raise ToolInputError(f"{key} exceeds its maximum length")
            if definition.get("format") == "date-time":
                _parse_time(value, key)
        elif definition["type"] == "object" and not isinstance(value, dict):
            raise ToolInputError(f"{key} must be an object")
    return checked


def _case() -> dict[str, Any]:
    bundle = build_synthetic_case_bundle()
    validate_case_bundle(bundle)
    return bundle


def _no_raw(value: Any) -> None:
    found: list[str] = []

    def inspect(item: Any) -> None:
        if isinstance(item, dict):
            found.extend(key for key in item if key in _RAW_FIELD_NAMES)
            for nested in item.values():
                inspect(nested)
        elif isinstance(item, list | tuple):
            for nested in item:
                inspect(nested)

    inspect(value)
    if found:
        raise RuntimeError(f"adapter projection attempted to expose prohibited source fields: {sorted(set(found))}")


class McpAdapter:
    """A stateless MCP request dispatcher over existing CareTrust services."""

    def __init__(self) -> None:
        self._compiler = CompilerService()
        self._app_compiler = ApplicationOnboardingCompiler()
        self._initialize_responded = False
        self._session_ready = False
        self._tool_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "caretrust_draft_delegation": self._draft_delegation,
            "caretrust_propose_app_profile": self._propose_app_profile,
            "caretrust_list_case_permissions": self._list_case_permissions,
            "caretrust_explain_decision": self._explain_decision,
            "caretrust_validate_case": self._validate_case,
            "caretrust_simulate_access": self._simulate_access,
            "caretrust_project_standards": self._project_standards,
        }

    def canonical_state_hash(self) -> str:
        """Hash the canonical state without retaining or changing it."""

        return str(_case()["bundle_sha256"])

    def handle_json(self, line: str) -> dict[str, Any] | None:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            return _error(-32700, "Parse error")
        return self.handle(request)

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict):
            return _error(-32600, "Invalid Request")
        request_id = request.get("id")
        notification = "id" not in request
        if request.get("jsonrpc") != JSONRPC_VERSION or not isinstance(request.get("method"), str):
            return None if notification else _error(-32600, "Invalid Request", request_id)
        method = request["method"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return None if notification else _error(-32602, "Invalid params", request_id)
        if method == "notifications/initialized":
            if self._initialize_responded and not params:
                self._session_ready = True
            return None
        if method == "initialize":
            if notification:
                return None
            if self._initialize_responded:
                return _error(-32600, "Initialize already completed", request_id)
            initialize_error = self._validate_initialize_params(params)
            if initialize_error is not None:
                return _error(-32602, initialize_error["message"], request_id, initialize_error.get("data"))
            self._initialize_responded = True
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": request_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
                    "instructions": "Read-only CareTrust adapter: draft, read, validate, explain, and simulate only. No authority-changing operations are available.",
                },
            }
        if not self._session_ready:
            return None if notification else _error(
                -32002,
                "Server not initialized",
                request_id,
                {"required": ["initialize", "notifications/initialized"]},
            )
        if method == "tools/list":
            if notification:
                return None
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": {"tools": list(TOOL_DEFINITIONS)}}
        if method == "tools/call":
            if notification:
                return None
            return self._call_tool(request_id, params)
        return None if notification else _error(-32601, "Method not found", request_id)

    @staticmethod
    def _validate_initialize_params(params: dict[str, Any]) -> dict[str, Any] | None:
        required = {"protocolVersion", "capabilities", "clientInfo"}
        missing = required - set(params)
        if missing:
            return {"message": "Invalid initialize parameters", "data": {"missing": sorted(missing)}}
        requested = params["protocolVersion"]
        if not isinstance(requested, str):
            return {"message": "Invalid initialize protocolVersion"}
        if requested != MCP_PROTOCOL_VERSION:
            return {
                "message": "Unsupported protocol version",
                "data": {"supported": [MCP_PROTOCOL_VERSION], "requested": requested},
            }
        if not isinstance(params["capabilities"], dict):
            return {"message": "Invalid initialize capabilities"}
        client_info = params["clientInfo"]
        if not isinstance(client_info, dict):
            return {"message": "Invalid initialize clientInfo"}
        for field in ("name", "version"):
            if not isinstance(client_info.get(field), str) or not client_info[field]:
                return {"message": "Invalid initialize clientInfo", "data": {"required": ["name", "version"]}}
        return None

    def _call_tool(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or name not in self._tool_handlers:
            result = _tool_result(
                {
                    "evidence_status": "executed_local",
                    "error_code": "TOOL_NOT_ALLOWED",
                    "non_claim": "This adapter exposes no authority-changing or unknown tools.",
                },
                is_error=True,
            )
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}
        if set(params) - {"name", "arguments"}:
            result = _tool_result({"error_code": "INVALID_TOOL_CALL", "message": "tools/call accepts only name and arguments."}, is_error=True)
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}
        try:
            args = _validate_args(name, params.get("arguments", {}))
            value = self._tool_handlers[name](args)
            _no_raw(value)
            result = _tool_result(value)
        except ToolInputError as exc:
            result = _tool_result({"error_code": "INVALID_TOOL_ARGUMENTS", "message": str(exc)}, is_error=True)
        except (ValueError, KeyError) as exc:
            result = _tool_result({"error_code": "TOOL_EVALUATION_DENIED", "message": str(exc)}, is_error=True)
        except RuntimeError:
            # Never serialize internal projection/leakage diagnostics to a client.
            result = _tool_result(
                {"error_code": "TOOL_INTERNAL_DENIED", "message": "Tool output was denied by the read-only safety boundary."},
                is_error=True,
            )
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}

    def _draft_delegation(self, args: dict[str, Any]) -> dict[str, Any]:
        now = _parse_time(args["created_at"], "created_at")
        intent = make_intent_statement(
            intent_id=args["intent_id"], patient_ref=args["patient_ref"], utterance=args["utterance"], created_at=now
        )
        compilation = self._compiler.compile_intent(intent, now=now)
        return {
            "evidence_status": compilation.evidence_status,
            "operation": "draft_delegation",
            "draft": compilation.draft.model_dump(mode="json"),
            "clarifications": [item.model_dump(mode="json") for item in compilation.clarifications],
            "safety_flags": list(compilation.safety_flags),
            "non_claims": list(compilation.non_claims),
        }

    def _propose_app_profile(self, args: dict[str, Any]) -> dict[str, Any]:
        now = _parse_time(args["created_at"], "created_at")
        source = make_application_description(
            application_id=args["application_id"], source_id=args["source_id"], description=args["description"], openapi=args.get("openapi")
        )
        compilation = self._app_compiler.compile_application(source, now=now)
        return {
            "evidence_status": compilation.evidence_status,
            "operation": "propose_app_profile",
            "draft": compilation.draft.model_dump(mode="json"),
            "safety_flags": list(compilation.safety_flags),
            "non_claims": list(compilation.non_claims),
        }

    def _list_case_permissions(self, args: dict[str, Any]) -> dict[str, Any]:
        bundle = _case()
        rows = list(bundle["projections"]["applications"])
        caregiver = args.get("caregiver_ref")
        if caregiver is not None:
            rows = [row for row in rows if row["caregiver_ref"] == caregiver]
        return {
            "evidence_status": "executed_local",
            "operation": "read_permissions",
            "case_id": bundle["case_id"],
            "case_hash": bundle["bundle_sha256"],
            "permissions": rows,
            "non_claims": ["This is a minimum-data application projection, not the raw trust graph or source packet."],
        }

    def _explain_decision(self, args: dict[str, Any]) -> dict[str, Any]:
        bundle = _case()
        decision = next((item for item in bundle["decisions"] if item["decision_id"] == args["decision_id"]), None)
        if decision is None:
            raise ToolInputError("decision_id is not present in the canonical synthetic case")
        receipt = next(item for item in bundle["projections"]["applications"] if item["decision_id"] == decision["decision_id"])
        return {
            "evidence_status": decision["evidence_status"],
            "operation": "read_decision",
            "case_id": bundle["case_id"],
            "decision": {
                key: decision[key]
                for key in ("decision_id", "request_id", "decision", "reason_code", "policy_id", "policy_version", "as_of", "supporting_canonical_ids")
            },
            "minimum_data_receipt": receipt["minimum_data"],
            "withheld": ["source_document_packet", "unreviewed_extraction", "unrelated_claims", "clinical_holder_payload"],
            "non_claims": ["Explanation does not issue a token, replay a prior permit, or authorize a new request."],
        }

    def _validate_case(self, args: dict[str, Any]) -> dict[str, Any]:
        bundle = _case()
        validate_case_bundle(bundle)
        return {
            "evidence_status": "executed_local",
            "operation": "validate_contract",
            "case_id": bundle["case_id"],
            "case_hash": bundle["bundle_sha256"],
            "valid": True,
            "validated_contract": "caretrust.synthetic-case-bundle.v1",
            "non_claims": ["Local validation is not external standards conformance certification."],
        }

    def _simulate_access(self, args: dict[str, Any]) -> dict[str, Any]:
        bundle = _case()
        objects = bundle["canonical_objects"]
        request = next((item for item in objects["permission_requests"] if item["request_id"] == args["request_id"]), None)
        if request is None:
            raise ToolInputError("request_id is not present in the canonical synthetic case")
        canonical_decision = next(item for item in bundle["decisions"] if item["request_id"] == args["request_id"])
        as_of = _parse_time(args["as_of"], "as_of") if "as_of" in args else _parse_time(canonical_decision["as_of"], "canonical decision time")
        relationship = objects["relationship_claim"]
        delegation = objects["delegation_grant"]
        credential = objects["credential_claim"]
        assignment = objects["agency_assignment"] if request["authority_path"] == "workforce_assignment_v1" else objects["respite_assignment"]
        service_grant = objects["agency_service_grant"] if request["authority_path"] == "workforce_assignment_v1" else objects["respite_service_grant"]
        if request["authority_path"] == "family_delegation_v1" and as_of >= _parse_time(objects["delegation_revocation"]["revoked_at"], "delegation revocation time"):
            delegation = {**delegation, "status": "revoked", "revoked_at": objects["delegation_revocation"]["revoked_at"]}
        if request["authority_path"] == "workforce_assignment_v1" and as_of >= _parse_time(objects["credential_revocation"]["revoked_at"], "credential revocation time"):
            credential = {**credential, "status": "revoked", "revoked_at": objects["credential_revocation"]["revoked_at"]}
        if request["authority_path"] == "community_respite_v1" and as_of >= _parse_time(objects["respite_service_grant_revocation"]["revoked_at"], "respite revocation time"):
            service_grant = objects["respite_service_grant_revocation"]
        approved = {item["approved_item_id"]: item for item in objects["approved_document_items"]}
        decision = evaluate_case_permission(
            request,
            credential_claim=credential if request["authority_path"] == "workforce_assignment_v1" else None,
            relationship_claim=relationship if request["authority_path"] == "family_delegation_v1" else None,
            delegation_grant=delegation if request["authority_path"] == "family_delegation_v1" else None,
            assignment=assignment,
            service_grant=service_grant if request["authority_path"] != "family_delegation_v1" else None,
            approved_items=approved,
            as_of=as_of,
        )
        safe_decision = {key: value for key, value in decision.items() if key not in {"minimum_data", "supporting_canonical_ids"}}
        return {
            "evidence_status": decision["evidence_status"],
            "operation": "simulate_authorization",
            "simulation_only": True,
            "canonical_request_id": request["request_id"],
            "simulation": safe_decision,
            "authority_changed": False,
            "token_issued": False,
            "disclosure_returned": False,
            "non_claims": ["A simulation calls the existing deterministic policy but is not an authorization decision, token, or disclosure receipt."],
        }

    def _project_standards(self, args: dict[str, Any]) -> dict[str, Any]:
        bundle = _case()
        rows = list(bundle["projections"]["standards"])
        canonical_id = args.get("canonical_id")
        if canonical_id is not None:
            rows = [row for row in rows if row["canonical_id"] == canonical_id]
            if not rows:
                raise ToolInputError("canonical_id is not present in the published standards projection")
        return {
            "evidence_status": "executed_local",
            "operation": "read_projection",
            "case_id": bundle["case_id"],
            "standards_projection": rows,
            "semantic_loss": ["The projection is synthetic/local and does not represent a live standards exchange."],
            "non_claims": ["No FHIR server, HIE, production identity provider, or external conformance service was contacted."],
        }
