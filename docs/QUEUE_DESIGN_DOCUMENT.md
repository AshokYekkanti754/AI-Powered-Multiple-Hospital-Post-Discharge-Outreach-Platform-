# Queue Design Document

The platform uses tenant-scoped queue tasks ordered by clinical risk, follow-up urgency, campaign priority, and retry penalty. Redis atomic semaphores enforce each hospital's active-call capacity. Call outcomes move tasks through retry, callback, completion, dropped-call recovery, or manual follow-up states. A 90-second reclaimer prevents crashed workers from consuming capacity indefinitely.

Retry delays are 15, 45, and 120 minutes, rolled into permitted local calling hours. The Milestone 3.3 simulator exercises 25 tasks with constrained capacity and verifies zero orphaned slots.
