"""RFC 9457 *Problem Details* for API errors.

The contract with clients is the **`type`** — a stable URI reference like
``/errors/guardian-confirmation-needed``. A client (our web UI, or anyone else) maps that
to its own wording in its own language. The backend never ships the localized sentence as
the contract: ``title`` and ``detail`` are English, meant for logs, ``curl``, and as a
fallback when a client doesn't recognize the type.

So router code raises :class:`Problem` with a ``code`` and an English ``title`` — never a
sentence from `app/locales/` (`app/i18n.py`). Adding a language is then a frontend-only change.

    raise Problem(422, "guardian-confirmation-needed",
                  "A sailor under 18 needs a guardian's signature.")

The response body is::

    {
      "type": "/errors/guardian-confirmation-needed",
      "title": "A sailor under 18 needs a guardian's signature.",
      "status": 422,
      "detail": "Toni Groth turns 18 after this event.",   # optional, instance-specific
      "instance": "/api/events/12/waiver",
      "person_id": 42                                        # optional extension members
    }

No router raises a plain ``HTTPException`` (ruff's banned-api rule in ``pyproject.toml``
refuses the import). The framework still does — an unknown route, a wrong method — and
those, like request-validation errors, are rendered as ``application/problem+json`` too
(see ``app.main``), with a generic ``/errors/http-<status>`` or ``/errors/validation``.

The OpenAPI document declares these responses on every operation
(:func:`declare_problems`), so a generated client sees the problem shape rather than
only FastAPI's ``HTTPValidationError``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, NamedTuple

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

# Relative reference (RFC 9457 §3.1 permits it). Clients care about the last segment —
# the code — not the origin.
ERROR_BASE = "/errors/"

CONTENT_TYPE = "application/problem+json"


class Problem(Exception):
    """An error that carries a machine-readable ``code`` for clients to localize."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        *,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        self.status = status
        # kebab-case, stable, unique. This is the API contract — never rename lightly.
        self.code = code
        # Short English summary of the *type*, not of this one occurrence.
        self.title = title
        # Optional English elaboration about this specific occurrence.
        self.detail = detail
        self.headers = headers
        # Extension members merged into the body (e.g. person_id, required_version).
        self.extra = extra
        super().__init__(f"{code}: {title}")

    @property
    def type(self) -> str:
        return f"{ERROR_BASE}{self.code}"

    def body(self, instance: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
        }
        if self.detail:
            out["detail"] = self.detail
        if instance:
            out["instance"] = instance
        out.update(self.extra)
        return out

    def response(self, instance: str | None = None) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            content=self.body(instance),
            headers=self.headers,
            media_type=CONTENT_TYPE,
        )


async def problem_handler(request: Request, exc: Problem) -> JSONResponse:
    return exc.response(instance=request.url.path)


def http_problem_body(status_code: int, detail: Any, instance: str) -> dict[str, Any]:
    """A problem body for a plain ``HTTPException``.

    ``detail`` is preserved verbatim so clients reading ``body.detail`` keep working; the
    ``type`` is a generic ``/errors/http-<status>`` until the route adopts a real code.
    """
    body: dict[str, Any] = {
        "type": f"{ERROR_BASE}http-{status_code}",
        "title": _HTTP_TITLES.get(status_code, "Request failed"),
        "status": status_code,
        "instance": instance,
    }
    if detail is not None:
        body["detail"] = detail
    return body


_HTTP_TITLES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Not allowed",
    404: "Not found",
    409: "Conflict",
    422: "Request could not be processed",
    500: "Internal error",
}


class ProblemDetails(BaseModel):
    """An RFC 9457 problem — the body of every error response, for the OpenAPI document.

    Only for documentation: :class:`Problem` builds the body. Extension members (named in
    each code's raise site) are allowed, which is what ``extra="allow"`` says.
    """

    model_config = ConfigDict(extra="allow")

    type: str = Field(description="`/errors/<code>` — the stable contract a client maps.")
    title: str = Field(description="Short English summary of the type; a fallback.")
    status: int
    detail: str | list[dict[str, Any]] | None = Field(
        default=None,
        description="English elaboration of this occurrence; for `/errors/validation` the "
        "per-field list.",
    )
    instance: str | None = Field(default=None, description="The request path.")


class Operation(NamedTuple):
    """One operation of the OpenAPI document, and what can refuse it."""

    path: str
    method: str
    #: Behind a guard of ``app/auth.py``: can answer 401 and 403.
    guarded: bool


_DESCRIPTIONS = {
    401: "Not signed in, or the session is no longer valid.",
    403: "Signed in, but lacking the relation this needs.",
    404: "Something the path names does not exist.",
    409: "Conflicts with the current state.",
    422: "The request could not be processed.",
}


def declare_problems(openapi: dict[str, Any], operations: Iterable[Operation]) -> None:
    """Adds the error responses an operation can give to the OpenAPI document, each as
    ``application/problem+json`` with :class:`ProblemDetails`.

    401/403 for guarded operations, 404 where the path names something, 409 for writes,
    422 for all — replacing FastAPI's own ``HTTPValidationError``, which is not the shape
    this API answers with (``app.main`` renders validation errors as problems).
    """
    schemas = openapi.setdefault("components", {}).setdefault("schemas", {})
    schemas["ProblemDetails"] = ProblemDetails.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    content = {CONTENT_TYPE: {"schema": {"$ref": "#/components/schemas/ProblemDetails"}}}
    for operation in operations:
        spec = openapi.get("paths", {}).get(operation.path, {}).get(operation.method.lower())
        if spec is None:
            continue
        statuses = [422]
        if operation.guarded:
            statuses += [401, 403]
        if "{" in operation.path:
            statuses.append(404)
        if operation.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            statuses.append(409)
        responses = spec.setdefault("responses", {})
        for status in sorted(statuses):
            responses[str(status)] = {"description": _DESCRIPTIONS[status], "content": content}
    # FastAPI's validation shapes, once nothing refers to them any more.
    for name in ("HTTPValidationError", "ValidationError"):
        if f'"#/components/schemas/{name}"' not in json.dumps(openapi):
            schemas.pop(name, None)
