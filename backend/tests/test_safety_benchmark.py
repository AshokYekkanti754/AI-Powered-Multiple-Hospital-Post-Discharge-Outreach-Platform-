from app.safety.evaluation_runner import run_evaluation, render_report
from app.safety.metrics import ConfusionMatrix, calculate_metrics


def test_false_negative_rate_formula():
    result = calculate_metrics([True, True, False, False], [True, False, True, False])
    assert result.true_positives == 1
    assert result.false_negatives == 1
    assert result.false_positive == result.false_positives if hasattr(result, "false_positive") else result.false_positives == 1
    assert result.false_negative_rate == 0.5


def test_fixed_safety_dataset_runs_end_to_end():
    matrix, results = run_evaluation()
    assert len(results) == 30
    assert matrix.false_negative_rate == 0.0
    assert "Escalation false-negative rate" in render_report(matrix, results)
