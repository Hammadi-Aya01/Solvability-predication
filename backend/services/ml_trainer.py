"""
services/ml_trainer.py
Re-exports training pipeline from ml code.
The actual implementation is the code from the provided source txt.
"""
from services.ml_pipeline import run_training_pipeline, TrainingReport, ModelResult

__all__ = ["run_training_pipeline", "TrainingReport", "ModelResult"]
