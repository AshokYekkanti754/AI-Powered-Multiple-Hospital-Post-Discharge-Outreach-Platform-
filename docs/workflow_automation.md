# Workflow Automation - Milestone 2.3

## Event contract

`DomainEvent` carries an immutable `event_id`, `event_type`, `hospital_id`, payload, and UTC timestamp. The event bus keeps processed IDs and ignores duplicate deliveries. Supported operational event names are `CALL_COMPLETED`, `CALL_NO_ANSWER`, and `ESCALATION_CREATED`.

The event bus is intentionally transport-neutral. The in-process registry is used by tests and local development; Celery/Redis can deliver the same event payload asynchronously in production.

## Escalation lifecycle

```text
OPEN -> ACKNOWLEDGED -> IN_REVIEW -> RESOLVED
```

Escalations are always tenant-scoped and carry patient, campaign, and optional call identifiers. Creating an escalation writes an `escalations` row and an in-app notification for active clinical reviewers and hospital administrators. Acknowledgement records the acting user and timestamp; resolution records the clinical notes.

## Timeout chain

Urgent or otherwise open escalations can be checked after 15 minutes by `escalation_timeout_worker.py`. If the row is still `OPEN`, a backup in-app alert is sent to hospital staff. Acknowledged or resolved rows are ignored, which makes acknowledgement an effective cancellation of the backup action.

## Authorization

List, acknowledgement, and resolution queries include `hospital_id` from the JWT tenant context. Only `HOSPITAL_ADMIN` and `CLINICAL_REVIEWER` roles can change escalation state. Notification reads are filtered by both tenant and recipient user ID.
