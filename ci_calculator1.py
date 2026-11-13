from collections import defaultdict
import math

import numpy as np
from scipy import stats


def calculate_confidence_intervals(
    measurements,
    treatments,
    trials,
    metric="yield_value",
    confidence=0.95,
):
    """Calculate a t-based confidence interval for each trial/treatment group.

    Each measurement must reference a treatment_id. Treatment rows link that
    measurement to a trial and treatment name. Groups with fewer than two
    numeric observations return a mean and sample size, but no interval yet.
    """
    trial_code_by_id = {
        str(row.get("trial_id")): row.get("trial_code")
        for row in trials
    }
    treatment_by_id = {
        str(row.get("treatment_id")): row
        for row in treatments
    }

    grouped_values = defaultdict(list)
    labels = {}

    for row in measurements:
        value = row.get(metric)
        if value is None:
            continue

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric_value):
            continue

        treatment = treatment_by_id.get(str(row.get("treatment_id")))
        if treatment is None:
            continue

        trial_id = str(treatment.get("trial_id"))
        trial_code = trial_code_by_id.get(trial_id)
        treatment_name = (treatment.get("treatment_name") or "Unnamed treatment").strip()

        # A repeated trial code identifies submissions belonging to the same
        # study, even if the current form creates a new trial row per submission.
        study_key = str(trial_code).strip() if trial_code else trial_id
        group_key = (study_key, treatment_name)
        grouped_values[group_key].append(numeric_value)
        labels[group_key] = {
            "trial_code": trial_code or trial_id,
            "treatment": treatment_name,
        }

    output = []
    for group_key in sorted(grouped_values, key=lambda key: (key[0], key[1].lower())):
        values = grouped_values[group_key]
        n = len(values)
        mean = float(np.mean(values))
        margin = None

        if n >= 2:
            standard_error = float(stats.sem(values))
            critical_value = float(stats.t.ppf((1 + confidence) / 2, n - 1))
            margin = standard_error * critical_value

        group = labels[group_key]
        output.append({
            "trial_code": group["trial_code"],
            "treatment": group["treatment"],
            "sample_size": n,
            "mean": round(mean, 2),
            "margin": round(margin, 2) if margin is not None else None,
            "lower_bound": round(mean - margin, 2) if margin is not None else None,
            "upper_bound": round(mean + margin, 2) if margin is not None else None,
        })

    return output


class ConfidenceIntervalTracker:
    """Small in-memory helper for experiments; app dashboards use saved DB rows."""

    def __init__(self, confidence=0.95):
        self.values = []
        self.confidence = confidence

    def add_data(self, new_values):
        if isinstance(new_values, list):
            self.values.extend(new_values)
        else:
            self.values.append(new_values)
        return self.recalculate()

    def recalculate(self):
        values = []
        for value in self.values:
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                values.append(value)

        n = len(values)
        if n < 2:
            return None

        mean = float(np.mean(values))
        margin = float(stats.sem(values) * stats.t.ppf(0.975, n - 1))
        return {
            "sample_size": n,
            "mean": round(mean, 2),
            "confidence_interval_margin": round(margin, 2),
            "lower_bound": round(mean - margin, 2),
            "upper_bound": round(mean + margin, 2),
        }


if __name__ == "__main__":
    tracker = ConfidenceIntervalTracker()
    print(tracker.add_data([10, 12, 11, 9]))
    print(tracker.add_data(15))
