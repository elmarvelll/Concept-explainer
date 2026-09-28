import logging
import os

import jwt
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

# Shared with the Next.js backend (see frontend/lib/auth-token.ts), which
# signs this JWT after verifying the browser's session — this service never
# talks to NextAuth or the user DB directly, it only trusts this signature.
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"


async def require_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency that verifies the Next.js-issued JWT on every request.

    Raises 401 if the header is missing, malformed, expired, or the
    signature doesn't match `JWT_SECRET`. On success, returns the token's
    claims (at minimum `sub` — the authenticated user's id — and `email`).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        logger.warning("Rejected request with invalid JWT")
        raise HTTPException(status_code=401, detail="Invalid token")

    return claims
