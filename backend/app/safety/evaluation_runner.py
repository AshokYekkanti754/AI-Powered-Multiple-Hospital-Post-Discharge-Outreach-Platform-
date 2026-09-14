from __future__ import annotations
import json
from pathlib import Path
from app.ai.consensus_council import TriageDecision, TriageStatus, run_consensus
from app.safety.metrics import ConfusionMatrix, calculate_metrics

DATASET = Path(__file__).with_name("test_cases.json")


def _assess(transcript: str) -> TriageDecision:
    lowered = transcript.lower()
    urgent = any(term in lowered for term in ("chest pain", "cannot breathe", "severe bleeding", "unclear", "uncertain", "ambiguous", "possible", "new symptom"))
    return TriageDecision(status=TriageStatus.URGENT if urgent else TriageStatus.ROUTINE)


def run_evaluation(path: Path = DATASET) -> tuple[ConfusionMatrix, list[dict]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    expected, predicted = [], []
    results = []
    for case in cases:
        try:
            result = run_consensus(case["transcript"], [_assess, _assess, _assess])
            decision = result.human_escalation
        except Exception:
            decision = True
        expected.append(bool(case["expected_escalation"]))
        predicted.append(decision)
        results.append({"id": case["id"], "expected": expected[-1], "predicted": decision, "false_negative": expected[-1] and not decision})
    return calculate_metrics(expected, predicted), results


def render_report(matrix: ConfusionMatrix, results: list[dict]) -> str:
    false_negatives = [row["id"] for row in results if row["false_negative"]]
    return "\n".join(["# Safety Evaluation Report", "", f"- Cases: {len(results)}", f"- True positives: {matrix.true_positives}", f"- False positives: {matrix.false_positives}", f"- True negatives: {matrix.true_negatives}", f"- False negatives: {matrix.false_negatives}", f"- Escalation false-negative rate: {matrix.false_negative_rate:.4f}", "", "## False negatives", "None" if not false_negatives else ", ".join(false_negatives)])
