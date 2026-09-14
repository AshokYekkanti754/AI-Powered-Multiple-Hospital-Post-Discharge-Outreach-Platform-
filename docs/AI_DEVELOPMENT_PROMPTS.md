# AI Development Prompts

## Voice intake
Extract identity verification, raw symptoms, and transcript without making a clinical disposition.

## Clinical triage
Retrieve only the authenticated hospital's protocols, cite matched documents, and emit a structured routine, concerning, urgent, or uncertain status.

## Consensus council
Run three independent assessments. Unanimous routine may remain routine; any urgent/concerning/uncertain result or disagreement requires escalation and arbiter review.

## Documentation
Convert the transcript and disposition into a structured clinical note and use only the controlled EHR tool boundary for write-back.

Malformed or failed outputs default to human escalation.
