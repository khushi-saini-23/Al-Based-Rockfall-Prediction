"""Comparable RF/XGB research training; never run on synthetic demo event labels."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier

from .config import MLConfig, MODELS, PROJECT
from .data import align_measurements
from .evaluate import chronological_split, event_detection, score
from .features import make_features
from .targets import build_targets, read_labels


def prepare(config: MLConfig, *, fixture: bool = False):
    if not fixture:
        real_root = (PROJECT / "datasets" / "real").resolve()
        data_path = config.data_dir.resolve()
        if not config.reviewed_real_data or data_path != real_root:
            raise ValueError("Training requires reviewed_real_data=true and datasets/real; demo data is prohibited")
        if config.decision_threshold is None or not config.decision_threshold_rationale:
            raise ValueError("A reviewed, justified decision_threshold and rationale are required before real-data training")
    aligned = align_measurements(config, fixture=fixture)
    features, names = make_features(aligned, config)
    if config.feature_names is not None:
        unknown = set(config.feature_names) - set(names)
        if unknown:
            raise ValueError(f"Configured features are unavailable: {sorted(unknown)}")
        names = config.feature_names
    events, coverage = read_labels(config.data_dir / "rockfall_events" / "events.csv",
                                   config.data_dir / "rockfall_events" / "coverage.csv", fixture=fixture)
    labelled = build_targets(features, events, coverage, config.horizon_hours)
    if labelled.target.notna().sum() < 30 or labelled.target.dropna().nunique() < 2:
        raise ValueError("Insufficient verified positive and negative examples for training")
    return labelled, names, events


def _candidates(name: str, ratio: float, seed: int):
    if name == "random_forest":
        base = {"n_estimators": 120, "max_depth": 8, "min_samples_split": 4,
                "min_samples_leaf": 2, "max_features": "sqrt", "class_weight": "balanced_subsample", "random_state": seed, "n_jobs": -1}
        return [base, {**base, "n_estimators": 200, "max_depth": 12, "min_samples_leaf": 4,
                       "min_samples_split": 8, "max_features": 0.7, "class_weight": "balanced"}]
    base = {"n_estimators": 180, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8,
            "colsample_bytree": 0.8, "min_child_weight": 2, "reg_lambda": 2.0,
            "scale_pos_weight": ratio, "random_state": seed, "n_jobs": -1, "eval_metric": "logloss"}
    return [base, {**base, "n_estimators": 280, "max_depth": 4, "learning_rate": 0.035, "min_child_weight": 4}]


def _fit(name: str, params: dict, x, y, *, early_x=None, early_y=None):
    options = dict(params)
    if name == "random_forest":
        model = RandomForestClassifier(**options)
        model.fit(x, y)
        return model
    if early_x is not None and len(np.unique(early_y)) == 2 and len(early_y) >= 30:
        options["early_stopping_rounds"] = 15
        model = XGBClassifier(**options)
        model.fit(x, y, eval_set=[(early_x, early_y)], verbose=False)
        return model
    model = XGBClassifier(**options)
    model.fit(x, y, verbose=False)
    return model


def _train_one(name: str, train, validation, test, feature_names, events, config, output_dir, *, fixture: bool):
    # Tuning uses only the training period. Its final fifth is a chronological internal holdout.
    inner_train, inner_validation, _ = chronological_split(train, config.horizon_hours, 0.2, 0.15)
    if inner_train.target.nunique() < 2:
        raise ValueError("Training fold lacks both event classes")
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    x_inner = imputer.fit_transform(inner_train[feature_names])
    x_tune = imputer.transform(inner_validation[feature_names])
    ratio = max(1.0, float((inner_train.target == 0).sum() / max(1, (inner_train.target == 1).sum())))
    threshold = config.decision_threshold if config.decision_threshold is not None else 0.5
    trials = []
    configured = config.rf_candidates if name == "random_forest" else config.xgb_candidates
    candidates = [{**_candidates(name, ratio, config.seed)[0], **item} for item in configured] if configured else _candidates(name, ratio, config.seed)
    for params in candidates:
        candidate = _fit(name, params, x_inner, inner_train.target.astype(int).to_numpy(),
                         early_x=x_tune if name == "xgboost" else None,
                         early_y=inner_validation.target.astype(int).to_numpy())
        measured = score(inner_validation.target.astype(int), candidate.predict_proba(x_tune)[:, 1], threshold)
        trials.append((measured["pr_auc"] if measured["pr_auc"] is not None else -1,
                       measured["recall"] if measured["recall"] is not None else -1, params, candidate))
    _, _, selected_params, tuned_model = max(trials, key=lambda item: (item[0], item[1]))
    if name == "xgboost" and hasattr(tuned_model, "best_iteration"):
        selected_params = {**selected_params, "n_estimators": tuned_model.best_iteration + 1}
    final_imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    x_train = final_imputer.fit_transform(train[feature_names])
    x_validation = final_imputer.transform(validation[feature_names])
    x_test = final_imputer.transform(test[feature_names])
    model = _fit(name, selected_params, x_train, train.target.astype(int).to_numpy())
    validation_scores = model.predict_proba(x_validation)[:, 1]
    test_scores = model.predict_proba(x_test)[:, 1]
    validation_metrics = score(validation.target.astype(int), validation_scores, threshold)
    test_metrics = score(test.target.astype(int), test_scores, threshold)
    test_metrics.update(event_detection(events, test, test_scores, threshold, config.horizon_hours))
    importance = sorted(({"feature": feature, "importance": float(value)}
                         for feature, value in zip(feature_names, model.feature_importances_)),
                        key=lambda item: item["importance"], reverse=True)
    metadata = {"model_name": name, "model_version": config.model_version,
                "prediction_source": "NON_DEPLOYABLE_TEST_FIXTURE" if fixture else "EXPERIMENTAL_ML",
                "validation_status": "software_test_only" if fixture else "research_unvalidated",
                "trained_at": datetime.now(timezone.utc).isoformat(), "horizon_hours": config.horizon_hours,
                "feature_names": feature_names, "decision_threshold": threshold,
                "decision_threshold_rationale": config.decision_threshold_rationale or "unit-test fixture threshold only",
                "probabilities_calibrated": False, "dataset_provenance": "unit_test_fixture" if fixture else "real_observed",
                "train_rows": len(train), "validation_rows": len(validation), "test_rows": len(test),
                "parameters": selected_params, "validation_metrics": validation_metrics, "test_metrics": test_metrics,
                "global_feature_importance": importance}
    artifact = {"imputer": final_imputer, "model": model, "metadata": metadata}
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{name}-{config.model_version}.joblib"
    joblib.dump(artifact, artifact_path)
    return metadata


def train_models(config: MLConfig, *, fixture: bool = False, output_dir: Path | None = None,
                 models: tuple[str, ...] = ("random_forest", "xgboost")) -> dict:
    if fixture and output_dir is None:
        raise ValueError("Fixture models need an explicit temporary output directory")
    if not models or set(models) - {"random_forest", "xgboost"}:
        raise ValueError("Select random_forest, xgboost, or both")
    labelled, feature_names, events = prepare(config, fixture=fixture)
    train, validation, test = chronological_split(labelled, config.horizon_hours,
                                                   config.validation_fraction, config.test_fraction)
    if train.target.nunique() < 2:
        raise ValueError("Training period needs verified positives and negatives")
    destination = output_dir or MODELS
    results = {name: _train_one(name, train, validation, test, feature_names, events, config, destination, fixture=fixture)
               for name in models}
    report = {"status": "software_test_only" if fixture else "research_unvalidated", "models": results,
              "selection": None, "reason": "No automatic model winner or safety approval; review missed events, alarms and site transfer."}
    (destination / "comparison.json").write_text(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train research RF and XGBoost only on reviewed real mine data")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--model", choices=("random_forest", "xgboost", "both"), default="both")
    args = parser.parse_args()
    try:
        names = ("random_forest", "xgboost") if args.model == "both" else (args.model,)
        report = train_models(MLConfig.from_json(args.config), models=names)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(2, f"Training unavailable: {exc}\n")
    print(json.dumps(report, indent=2, default=str))
