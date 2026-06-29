"""
services/predictor.py
Re-exports ML inference functions from services/ml_predictor.py.
ml_predictor.py is the ONLY inference engine — ml_service.py logic
has been merged into it (encoding + SHAP).
"""
from services.ml_predictor import (
    load_model,
    activate_model,
    get_active_model,
    is_ready,
    predict,
    predict_batch,
    compute_psi,
    detect_drift,
    LoadedModel,
)

__all__ = [
    "load_model", "activate_model", "get_active_model",
    "is_ready", "predict", "predict_batch",
    "compute_psi", "detect_drift", "LoadedModel",
]
