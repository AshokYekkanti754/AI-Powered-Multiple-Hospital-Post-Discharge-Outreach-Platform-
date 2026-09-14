"""
Shared FastAPI dependencies: DB session, current tenant context, and
role-gating helpers used across endpoints.
"""
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models.user import UserRole
from app.db.session import get_db
from app.middleware.tenant import TenantContext


def get_current_context(request: Request) -> TenantContext:
    context = getattr(request.state, "tenant_context", None)
    if context is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return context


def require_roles(*allowed_roles: UserRole):
    def _dependency(context: TenantContext = Depends(get_current_context)) -> TenantContext:
        if context.role not in {r.value for r in allowed_roles}:
            raise HTTPException(status_code=403, detail="Insufficient role permissions")
        return context

    return _dependency


# Keep this as an alias so FastAPI dependency overrides for get_db apply to
# every endpoint that imports db_session.
db_session = get_db
