"""RFC 9457 *Problem Details* for API errors.

The contract with clients is the **`type`** — a stable URI reference like
``/errors/guardian-confirmation-needed``. A client (our web UI, or anyone else) maps that
to its own wording in its own language. The backend never ships the localized sentence as
the contract: ``title`` and ``detail`` are English, meant for logs, ``curl``, and as a
fallback when a client doesn't recognize the type.

So router code raises :class:`Problem` with a ``code`` and an English ``title`` — never a
``tr(locale, …)`` sentence. Adding a language is then a frontend-only change.

    raise Problem(422, "guardian-confirmation-needed",
                  "A sailor under 18 needs a guardian's signature.")

The response body is::

    {
      "type": "/errors/guardian-confirmation-needed",
      "title": "A sailor under 18 needs a guardian's signature.",
      "status": 422,
      "detail": "Toni Groth turns 18 after this event.",   # optional, instance-specific
      "instance": "/api/events/12/waiver",
      "sailor_id": 42                                        # optional extension members
    }

Plain ``HTTPException`` and request-validation errors are also rendered as
``application/problem+json`` (see ``app.main``), keeping ``detail`` where it was so
existing clients keep working while routers migrate to typed codes one at a time.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

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
        # Extension members merged into the body (e.g. sailor_id, required_version).
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
