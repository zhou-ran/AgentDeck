"""Authentication middleware for AgentStatus.

Skip auth for localhost (127.0.0.1 / ::1 / localhost).
For LAN access, require Bearer token.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.security import get_token

_bearer = HTTPBearer(auto_error=False)

_LOCALHOST = {"127.0.0.1", "localhost", "::1"}


def _is_localhost(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in _LOCALHOST


def require_token():
    """Dependency that validates Bearer token. Skipped for localhost."""

    async def _check(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Security(_bearer),
    ):
        # Skip auth for localhost access (dashboard in browser)
        if _is_localhost(request):
            return

        token = get_token()
        supplied_token = credentials.credentials if credentials else request.query_params.get("token", "")
        if not supplied_token or not secrets.compare_digest(supplied_token, token):
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    return Depends(_check)
