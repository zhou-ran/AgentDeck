from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import get_or_create_token, get_host

_bearer = HTTPBearer(auto_error=False)


def require_token():
    """Dependency that validates Bearer token. Skipped for localhost."""
    host = get_host()
    if host in ("127.0.0.1", "localhost", "::1"):
        # No auth needed on localhost
        return Depends(lambda: None)

    async def _check(
        credentials: HTTPAuthorizationCredentials = Security(_bearer),
    ):
        token = get_or_create_token()
        if not credentials or credentials.credentials != token:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    return Depends(_check)
