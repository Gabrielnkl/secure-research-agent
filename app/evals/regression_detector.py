# app/evals/regression_detector.py
from app.evals.store import get_baseline_score

REGRESSION_THRESHOLD = 0.15  # Flag if score drops more than 15 points


def check_regression(run_id: str, current_score: float) -> tuple[bool, float | None]:
    """
    Returns (is_regression, delta).
    delta is negative when current score is lower than baseline.
    """
    baseline = get_baseline_score(run_id)
    if baseline is None:
        return False, None   # No history yet — first run

    delta = current_score - baseline
    is_regression = delta < -REGRESSION_THRESHOLD
    return is_regression, round(delta, 3)