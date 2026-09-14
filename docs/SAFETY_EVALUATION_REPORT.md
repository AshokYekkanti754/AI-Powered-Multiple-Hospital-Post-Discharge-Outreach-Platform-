# Safety Evaluation Report

The fixed benchmark contains 30 annotated routine, concerning, urgent, and ambiguous cases. The evaluation runner computes TP, FP, TN, FN and escalation false-negative rate as `FN / (TP + FN)`. The deterministic safety adapter currently produces zero false negatives on the fixed dataset; external model performance must be evaluated separately before production use.

The consensus council escalates on urgent/concerning/uncertain output, disagreement, malformed output, or model failure. This is a conservative development baseline, not a clinical validation claim.
