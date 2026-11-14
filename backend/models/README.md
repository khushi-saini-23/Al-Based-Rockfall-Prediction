# Research model artifacts

No model is currently installed or activated. Only research models trained on
reviewed real observations may be saved here. `*.joblib` is ignored by Git.
Joblib loads pickle data, so place only trusted local artifacts in this folder.

After independent data and method review, a research model may be activated by
creating `active.json` with `{"artifact":"random_forest-research-v1.joblib"}`
or the corresponding XGBoost filename. Activation exposes an
`EXPERIMENTAL_ML` research endpoint; it never marks the model `VALIDATED_ML`,
calibrates probabilities, or enables automatic safety alerts.
