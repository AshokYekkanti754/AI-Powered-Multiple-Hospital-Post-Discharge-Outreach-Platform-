# Architecture — Milestone 1.1: Multi-Tenant Core & RBAC

## Request flow

```
Client Request
  -> TenantContextMiddleware (app/middleware/tenant.py)
       - reads "Authorization: Bearer <jwt>"
       - decode_access_token() -> {sub, role, hospital_id}
       - attaches request.state.tenant_context
       - public paths (login, /health, /docs) bypass this
  -> FastAPI dependency layer (app/api/v1/deps.py)
       - get_current_context(): pulls tenant_context, 401s if absent
       - require_roles(*roles): 403s if context.role not in allowed set
  -> Endpoint handler
       - reads context.hospital_id for scoping, NEVER a client-supplied
         hospital_id, for any non-PLATFORM_ADMIN caller
  -> SQLAlchemy query, explicitly filtered by hospital_id
  -> JSON response
```

## Tenant isolation boundary

The single rule this milestone enforces everywhere: **a non-PLATFORM_ADMIN
user's `hospital_id` comes only from their JWT, never from the request**.
Concretely:

- `GET /api/v1/users` filters `WHERE hospital_id = context.hospital_id`
  for every role except `PLATFORM_ADMIN`.
- `POST /api/v1/users` sets the new user's `hospital_id` to
  `context.hospital_id` — it is not an accepted field in the request body,
  so there's no payload shape that lets a Hospital Admin create a user in
  another hospital.
- `GET /api/v1/hospitals/me` resolves the hospital from context, not from
  a path parameter — there is no `GET /api/v1/hospitals/{id}` in this
  milestone precisely to avoid an ID-guessing vector before finer-grained
  authorization exists.
- `middleware/tenant.py` also exposes `enforce_same_hospital(context, id)`
  for any future endpoint (milestones 1.2+) that must accept an explicit
  `hospital_id` or resource-owning ID and needs to reject cross-tenant
  access with a 403 rather than silently scoping the query.

`PLATFORM_ADMIN` is the only role with `hospital_id = None` and the only
role allowed to see across tenants (hospital onboarding, full user list).

## Roles

| Role | hospital_id | Can onboard hospitals | Can create hospital users |
|---|---|---|---|
| PLATFORM_ADMIN | null | yes | n/a (not hospital-scoped) |
| HOSPITAL_ADMIN | own hospital | no | yes (own hospital only) |
| CAMPAIGN_MANAGER | own hospital | no | no |
| CLINICAL_REVIEWER | own hospital | no | no |

## Data model (this milestone only)

- `hospitals` — tenant root: name, timezone, concurrency/retry config,
  calling-hours window (used by later milestones' queue engine).
- `users` — `hospital_id` nullable only for PLATFORM_ADMIN; unique email;
  bcrypt `hashed_password`; `role` enum.
- `audit_logs` — generic append-only log (`hospital_id`, `user_id`,
  `action`, `resource`, `payload` JSON) scaffolded now, not yet written to
  by any endpoint — wiring this up is left to the milestone that
  introduces the first mutating clinical actions.

## Cross-DB compatibility note

Production uses PostgreSQL; the test suite uses in-memory SQLite for speed
and isolation. `app/db/base.py` defines a `GUID` `TypeDecorator` that maps
to native `UUID` on Postgres and `CHAR(36)` on SQLite, so the same model
code works unmodified against both.

## What's deliberately deferred

Per the milestone boundary: patients, encounters, campaigns, queue workers,
AI voice agents, LLM consensus, and EHR read/write are **not** implemented
here. `AuditLog` and `Hospital.max_concurrent_calls` / `retry_limit` /
calling-hours columns exist now because milestone 2.1's queue engine reads
them, but no queue logic is present in this milestone.

## Day 3 additions

The AI pipeline is provider-neutral and fail-closed. Protocol retrieval first
filters by the authenticated `hospital_id`, then ranks the tenant's documents.
The consensus council executes three independent assessors; any disagreement,
urgent/concerning/uncertain output, malformed output, timeout, or model error
routes to human escalation. AI requests write token, latency, cost, output,
and disagreement data to `ai_logs`.

Safety evaluation runs use a fixed 30-case dataset and persist confusion-matrix
metrics. Operational dashboards aggregate tenant-scoped queue and AI metrics.
The simulation and WebSocket surfaces are observability tools; they do not
grant AI components raw database or SQL access.
