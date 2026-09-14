# Queue Architecture - Milestone 2.1

## Priority formula

Each eligible encounter becomes one `queue_tasks` row. The scheduler orders pending rows by descending:

`score = (risk * 40) + (urgency * 35) + (campaign_priority / 5 * 15) - (retry_count * 10)`

`risk` is normalized to `[0, 1]`; percentage inputs from the Day 1 model are divided by 100. `urgency` is `1 - (time_remaining_hours / follow_up_window_hours)`, clamped to `[0, 1]`. Thus a high-risk patient close to window expiry outranks a routine patient even when entered later.

## Lifecycle

1. A campaign is created in `DRAFT`.
2. Starting a `DRAFT`, `READY`, or `PAUSED` campaign evaluates consent and the follow-up window, creates `PENDING` tasks, computes scores, and sets the campaign to `RUNNING`.
3. The scheduler claims the highest-scoring due task and marks it `CALLING`.
4. Pausing sets the campaign to `PAUSED`; the claim query only accepts tasks belonging to `RUNNING` campaigns, so no new tasks are popped while existing calls finish.
5. Completion of all tasks is reserved for the call lifecycle milestone.

## Concurrency control

Every tenant has a distinct Redis sorted-set key:

`lock:concurrency:{hospital_id}`

A Lua script removes expired tokens, checks `ZCARD` against `Hospital.max_concurrent_calls`, inserts a unique worker token, and sets a 30-second key TTL in one atomic operation. A worker only dispatches after acquiring a token. The token is removed on normal release; the TTL provides crash recovery. The implementation never shares capacity between hospital IDs.

Tests use the same semaphore contract through a locked in-memory implementation when Redis is unavailable. This makes the 100-worker stress test deterministic while production uses Redis.

## Worker boundary

Celery receives both `task_id` and `hospital_id`. The worker must retain the tenant ID for every downstream call and database query. Voice intake, clinical LLM prompts, and consensus workflows remain outside this milestone.

## Call lifecycle and retries

Call outcomes are persisted in `calls` and transition the related queue task:

```text
CALLING -> CONNECTED -> COMPLETED
CALLING -> NO_ANSWER/BUSY/VOICEMAIL -> RETRY_SCHEDULED
CALLING -> DROPPED -> RETRY_SCHEDULED (partial transcript preserved)
CALLING -> CALLBACK_SCHEDULED (patient-requested time)
RETRY_SCHEDULED -> MANUAL_FOLLOW_UP (retry limit reached)
```

Retry delays are 15, 45, and 120 minutes. A scheduled retry outside the hospital's local calling window rolls to the next business day's opening time. A dropped call keeps its partial transcript and receives a priority boost so reconnects are attempted promptly. Tasks left in `CALLING` for more than 90 seconds are reclaimed by the stuck-task worker.

## Event-driven escalations

Call events use idempotent `DomainEvent.event_id` values. `ESCALATION_CREATED` creates an escalation and in-app staff notifications. An open escalation is checked after 15 minutes; if it remains unacknowledged, the timeout worker sends a backup alert to hospital staff. Acknowledged and resolved records do not trigger the backup action.
