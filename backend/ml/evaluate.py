from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.calibration import calibration_curve


def chronological_split(frame: pd.DataFrame, horizon_hours: int, validation_fraction: float = 0.2,
                        test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eligible = frame[frame.target.notna()].sort_values("timestamp")
    times = eligible.timestamp.drop_duplicates().sort_values().reset_index(drop=True)
    if len(times) < 12:
        raise ValueError("Too few distinct observation times for chronological splitting")
    first_validation = times.iloc[int(len(times) * (1 - validation_fraction - test_fraction))]
    first_test = times.iloc[int(len(times) * (1 - test_fraction))]
    gap = pd.Timedelta(hours=horizon_hours)
    train = eligible[eligible.timestamp < first_validation - gap]
    validation = eligible[(eligible.timestamp >= first_validation) & (eligible.timestamp < first_test - gap)]
    test = eligible[eligible.timestamp >= first_test]
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Chronological split empty after prediction-horizon purge")
    return train, validation, test


def score(y_true, scores, threshold: float, *, sample_hours: float = 1) -> dict:
    truth = np.asarray(y_true, dtype=int)
    probability_score = np.asarray(scores, dtype=float)
    if len(truth) != len(probability_score) or not len(truth):
        raise ValueError("Scores and labels must be nonempty and aligned")
    predicted = (probability_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(truth, predicted, labels=[0, 1]).ravel()
    both_classes = len(np.unique(truth)) == 2
    has_positive = int(truth.sum()) > 0
    enough_for_calibration = int(truth.sum()) >= 100 and int((truth == 0).sum()) >= 100
    observed_rate, mean_score = calibration_curve(truth, probability_score, n_bins=5, strategy="quantile") if enough_for_calibration else ([], [])
    return {
        "precision": float(precision_score(truth, predicted, zero_division=0)) if (tp + fp) else None,
        "recall": float(recall_score(truth, predicted, zero_division=0)) if has_positive else None,
        "f1": float(f1_score(truth, predicted, zero_division=0)) if has_positive else None,
        "pr_auc": float(average_precision_score(truth, probability_score)) if both_classes else None,
        "roc_auc": float(roc_auc_score(truth, probability_score)) if both_classes else None,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "false_positives": int(fp), "false_negatives": int(fn),
        "false_alarms_per_monitored_zone_day": float(fp / (len(truth) * sample_hours / 24)) if sample_hours > 0 else None,
        "brier_score": float(brier_score_loss(truth, probability_score)) if enough_for_calibration else None,
        "calibration_bins": [{"mean_score": float(x), "observed_event_fraction": float(y)}
                             for x, y in zip(mean_score, observed_rate)] if enough_for_calibration else None,
        "positive_rows": int(truth.sum()), "rows": int(len(truth)),
        "threshold": threshold,
    }


def event_detection(events: pd.DataFrame, rows: pd.DataFrame, scores, threshold: float, horizon_hours: int) -> dict:
    """One event counts as detected if an earlier warning falls within its horizon."""
    if events.empty or rows.empty:
        return {"event_recall": None, "median_warning_lead_hours": None, "evaluated_events": 0}
    assessment = rows[["timestamp", "location_id"]].copy()
    assessment["warned"] = np.asarray(scores) >= threshold
    start, end = assessment.timestamp.min(), assessment.timestamp.max() + pd.Timedelta(hours=horizon_hours)
    relevant = events[(events.timestamp >= start) & (events.timestamp <= end)]
    leads = []
    for event in relevant.itertuples():
        warnings = assessment[(assessment.location_id == event.location_id) & assessment.warned &
                              (assessment.timestamp < event.timestamp) &
                              (assessment.timestamp >= event.timestamp - pd.Timedelta(hours=horizon_hours))]
        if not warnings.empty:
            leads.append((event.timestamp - warnings.timestamp.min()).total_seconds() / 3600)
    return {"event_recall": len(leads) / len(relevant) if len(relevant) else None,
            "median_warning_lead_hours": float(np.median(leads)) if leads else None,
            "evaluated_events": int(len(relevant))}
