"""Internal service-token authentication for the IT Ops API.

The backend and the ops API share a single token, configured via the
IT_OPS_API_TOKEN env var. Every request to /api/v1/* must carry it as
`X-Internal-Token`. Public health endpoints (/health/*) skip the check.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

EXPECTED_TOKEN = os.getenv("IT_OPS_API_TOKEN", "dev-local-only-token")


def require_service_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    if not EXPECTED_TOKEN:
        # If the server is misconfigured we fail closed.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is missing IT_OPS_API_TOKEN",
        )
    if x_internal_token != EXPECTED_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token header",
        )
