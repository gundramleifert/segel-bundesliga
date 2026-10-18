"""Response models shared by the sign-in routes (``/api/auth``, ``/api/dev``)."""

from __future__ import annotations

from pydantic import BaseModel


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
