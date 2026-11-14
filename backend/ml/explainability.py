"""Global impurity/gain importance and optional individual TreeSHAP attribution."""
from __future__ import annotations

import numpy as np


def explain_individual(model, transformed_row, feature_names: list[str]) -> dict:
    try:
        import shap

        values = shap.TreeExplainer(model).shap_values(transformed_row)
        if isinstance(values, list):
            values = values[-1]
        values = np.asarray(values)
        if values.ndim == 3:
            values = values[:, :, -1]
        contributions = values[0]
        ranked = sorted(zip(feature_names, contributions), key=lambda item: abs(float(item[1])), reverse=True)
        return {"status": "tree_shap_unvalidated", "top_contributing_features": [
            {"feature": name, "signed_contribution": float(value)} for name, value in ranked[:5]]}
    except Exception as exc:  # Optional SHAP must never block an assessment.
        return {"status": f"individual_explanation_unavailable: {type(exc).__name__}",
                "top_contributing_features": []}
