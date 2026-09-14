# EHR Boundary — Milestone 1.3

## Principle

AI agents (future milestones' voice agents / LLM consensus) are never given
a database session or a raw-SQL tool. Their only surface to the EHR is
`app/tools/ehr_tools.py` — three functions, each with a strict Pydantic
input schema and a fixed hospital_id supplied by the calling context, never
by the agent's own output.

```
AI Agent Tool Call
  -> Pydantic Input Schema (rejects malformed args before any DB touch)
  -> app.services.mock_ehr.* (enforces hospital_id ownership on every resource)
  -> ehr_audit_trail row written (success OR rejection — always exactly one)
  -> ToolResult{ok, data, error} returned to the agent
```

## Tool signatures

```python
get_patient_medical_history(patient_id: UUID) -> ToolResult
record_post_call_observation(patient_id: UUID, encounter_id: UUID, symptom: str, severity: Literal["mild","moderate","severe"]) -> ToolResult
create_clinical_followup_task(patient_id: UUID, reason: str) -> ToolResult
```

Every wrapper also takes `hospital_id` and `caller_agent_id` as explicit
keyword arguments supplied by the invoking service (never parsed from the
agent's free-text output) — this is what makes `enforce_same_hospital`-style
checks possible before any row is touched.

## Audit logging

`_audit()` in `ehr_tools.py` (and, on the plain HTTP API side, `_audit()` in
`api/v1/endpoints/ehr.py`) writes one `ehr_audit_trail` row per invocation:
`tool_name`, `caller_agent_id`, `action`, `input_params` (the validated
Pydantic payload, not raw input), and `status` — `"success"` or
`"rejected:<reason>"`. A validation failure (bad UUID, invalid enum value)
never reaches the DB and is therefore not audited — nothing was attempted
against a real resource, so there's nothing to log an outcome for. A
rejection caused by cross-tenant access, patient-not-found, etc. **is**
audited, since that is a real attempt against a real (if disallowed)
resource.

## Read vs. write endpoints

- **Read** (`GET /ehr/patients/{id}`, `GET /ehr/encounters/{id}`,
  `GET /ehr/observations`) — scoped to the caller's `hospital_id`; 403 if
  the resource belongs to another hospital, 404 if it doesn't exist at all.
- **Write** (`POST /ehr/communications`, `POST /ehr/observations`,
  `POST /ehr/tasks`) — same tenant check, plus an audit row on every call.

## What's deliberately deferred

No actual AI agent, LLM call, or voice pipeline exists yet — `ehr_tools.py`
is the interface those future milestones will call into. No Celery worker
or queue logic (Milestone 2.1) touches this file yet either.
