"""
services/prediction_service.py
Thin service layer between routes and the ML predictor.
Handles model loading, prediction dispatch, and drift checks.

FIX: load_active_model now correctly passes artifact_paths["shap_explainer"]
     to the explainer_path parameter (was silently missing before).
"""
from __future__ import annotations

from typing import Any

from models import MLModel


class PredictionService:

    # ── Model management ──────────────────────────────────────────────────

    @staticmethod
    def load_active_model(model: MLModel) -> None:
        """
        Load a persisted MLModel into the in-memory predictor registry
        and mark it as the active prediction engine.
        """
        from services.predictor import load_model, activate_model

        paths = model.artifact_paths or {}

        # FIX: require shap_explainer key explicitly
        _required = ["model", "scaler", "shap_explainer", "features", "encoders"]
        missing = [k for k in _required if k not in paths]
        if missing:
            raise ValueError(f"Artéfacts manquants dans artifact_paths: {missing}")

        key = load_model(
            model_path=paths["model"],
            scaler_path=paths["scaler"],
            explainer_path=paths["shap_explainer"],   # ← was silently wrong before
            features_path=paths["features"],
            encoders_path=paths["encoders"],
            threshold_path=paths.get("threshold"),
            model_version_id=model.id,
        )
        activate_model(key)

    @staticmethod
    def is_model_ready() -> bool:
        from services.predictor import is_ready
        return is_ready()

    @staticmethod
    def get_model_type() -> str | None:
        from services.predictor import get_active_model
        lm = get_active_model()
        return lm.model_type if lm else None

    # ── Prediction ────────────────────────────────────────────────────────

    @staticmethod
    def predict(client_data: dict) -> dict:
        from services.predictor import predict
        return predict(client_data)

    @staticmethod
    def predict_batch(records: list[dict]) -> list[dict]:
        from services.predictor import predict_batch
        return predict_batch(records)

    # ── Drift ─────────────────────────────────────────────────────────────

    @staticmethod
    def check_drift(df, feature_names: list[str]) -> dict:
        """
        Compare current DataFrame against model's training distribution.
        Uses PSI (Population Stability Index).
        """
        from services.predictor import get_active_model, detect_drift
        import pandas as pd

        lm = get_active_model()
        if lm is None:
            return {"error": "Aucun modèle actif"}

        try:
            scaler  = lm.scaler
            ref_data = {
                f: [float(lm.scaler.mean_[i])] * 100
                for i, f in enumerate(lm.features)
                if f in feature_names
            }
            ref_df = pd.DataFrame(ref_data)
        except Exception:
            ref_df = df.sample(min(50, len(df)))

        return detect_drift(ref_df, df, feature_names)
