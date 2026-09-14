from dataclasses import dataclass


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    @property
    def false_negative_rate(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.false_negatives / denominator if denominator else 0.0


def calculate_metrics(expected: list[bool], predicted: list[bool]) -> ConfusionMatrix:
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted lengths must match")
    tp = fp = tn = fn = 0
    for actual, decision in zip(expected, predicted):
        if actual and decision: tp += 1
        elif actual and not decision: fn += 1
        elif not actual and decision: fp += 1
        else: tn += 1
    return ConfusionMatrix(tp, fp, tn, fn)
