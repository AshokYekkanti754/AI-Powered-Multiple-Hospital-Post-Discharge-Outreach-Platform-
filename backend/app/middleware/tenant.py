"""
Tenant context middleware.

Extracts (user_id, role, hospital_id) from the validated JWT and attaches it
to `request.state.tenant_context`. Every downstream endpoint/query MUST read
tenant scoping from here rather than from client-supplied hospital_id values
(path params, query params, or body fields) — those are only ever used for a
*sub-selection within* the authenticated tenant, never to escape it.

Public routes (login, docs, health) are exempt.
"""
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import decode_access_token

PUBLIC_PATHS = {"/api/v1/auth/login", "/docs", "/openapi.json", "/health", "/api/v1/health", "/redoc"}


@dataclass
class TenantContext:
    user_id: str
    role: str
    hospital_id: str | None  # None only for PLATFORM_ADMIN


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            payload = decode_access_token(token)
        except ValueError:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

        request.state.tenant_context = TenantContext(
            user_id=payload["sub"],
            role=payload["role"],
            hospital_id=payload.get("hospital_id"),
        )
        return await call_next(request)


def enforce_same_hospital(context: TenantContext, target_hospital_id) -> None:
    """
    Raise if a non-platform-admin context is being used to touch a
    hospital_id other than its own. Call this from every endpoint/service
    that receives an explicit hospital_id (path/body) alongside the context.
    """
    from fastapi import HTTPException

    if context.role == "PLATFORM_ADMIN":
        return
    if context.hospital_id is None or str(context.hospital_id) != str(target_hospital_id):
        raise HTTPException(status_code=403, detail="Cross-tenant access is forbidden")
