# ML Assist Models

This folder holds optional models for the ML assist feature.

Files:
- gesture.joblib — classifier for gesture suggestions
- shout.joblib — classifier for shout suggestions

Workflow:
1. Enable feature logging in Rules Admin → Engine Config → ML assist.
2. Play and simulate to accumulate rows in `data/logs/ml/features.csv`.
3. Train models:
   - Use `scripts/train_ml_assist.py` to train logistic regression models.
   - Models will be saved here by default.
4. Validate in Admin ("ML Model Status & Quick Validation").
5. Carefully enable inference and per-stage toggles. Start with low weight (e.g., 0.25).

Notes:
- ML is additive; rules remain the source of truth. Guardrails prevent unsafe overrides.
- For talk stages, inference is often best disabled or weight kept low.
- You can delete models to turn status back to ❌ without changing config.
