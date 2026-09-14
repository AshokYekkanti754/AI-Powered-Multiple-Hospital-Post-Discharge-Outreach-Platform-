# Data Model — Milestone 1.2: FHIR-like Healthcare Resources

## Schema-to-FHIR resource mapping

| Table | FHIR-like resource | Key fields | Tenant FK |
|---|---|---|---|
| `patients` | Patient | mrn, name, phone, dob, preferred_language, consent_status | `hospital_id` (direct) |
| `encounters` | Encounter | discharge_timestamp, care_setting, risk_score, risk_tier, follow_up_window_hours | `hospital_id` (direct) |
| `conditions` | Condition | code, description | via `patient_id` -> patients.hospital_id |
| `observations` | Observation | observation_type, value, recorded_at | via `patient_id`/`encounter_id` |
| `care_plans` | CarePlan | status, instructions | via `patient_id`/`encounter_id` |

`patients` and `encounters` carry `hospital_id` directly (matching the
milestone's DB-changes spec) so tenant filtering never requires a join.
`conditions`, `observations`, and `care_plans` are scoped transitively
through their owning patient/encounter — every read path in
`patients.py` joins back to a `hospital_id`-scoped `Patient`/`Encounter`
row before returning child records, so a leaked `condition_id` or
`observation_id` alone can never be used to pull cross-tenant data.

## Risk tiers

`compute_risk_tier()` in `eligibility_engine.py` maps `risk_score` (0-100)
to `RiskTier`:

| risk_score | tier |
|---|---|
| 0–34.9 | LOW |
| 35–64.9 | MEDIUM |
| 65–84.9 | HIGH |
| 85–100 | CRITICAL |

## Eligibility rules

A patient/encounter is eligible for outreach when **all** of:
1. `patient.consent_status` is true.
2. `discharge_timestamp` is not in the future.
3. `now - discharge_timestamp <= follow_up_window_hours`.

Risk tier does **not** gate eligibility by itself — a LOW risk patient still
in-window is eligible, and a CRITICAL risk patient past the window is not.
This is intentional: window expiry and risk are independent signals; the
future queue engine (Milestone 2.1) is what combines them into a single
priority score.

## Ingestion behavior

`ingest_discharge_batch()` processes records one at a time inside a single
DB transaction, but catches and records per-record failures individually —
a batch of 220 records with 6 malformed rows still commits the 214 good
ones, per the milestone's error-handling requirement. See
`backend/data/seed_discharges.json` (220 simulated discharges split evenly
across "Hospital A" / "Hospital B", ~3% deliberately malformed) and
`backend/tests/test_patient_ingestion.py` for the tenant-partitioning proof.

## What's deliberately deferred

No campaign, queue, or outreach-attempt models exist yet — `/eligibility-check`
answers "is this patient contactable right now" but does not enqueue
anything. That's Milestone 2.1.
