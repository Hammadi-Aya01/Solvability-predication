"""
tests/test_prediction.py
Unit tests for the ML predictor (uses a tiny trained model in-memory).
Run with: pytest tests/
"""
import numpy as np
import pandas as pd
import pytest
import sys, os, pickle, tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _train_tiny_model():
    """Train a tiny RandomForest and return all artefact paths."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    import joblib, shap

    rng = np.random.default_rng(0)
    n   = 200
    X   = rng.random((n, 5))
    y   = (X[:, 0] + rng.random(n) > 1.0).astype(int)

    scaler = StandardScaler()
    Xs     = scaler.fit_transform(X)

    model  = RandomForestClassifier(n_estimators=10, random_state=0)
    model.fit(Xs, y)

    explainer = shap.TreeExplainer(model)
    encoders  = {}
    features  = [f"F{i}" for i in range(5)]

    tmpdir = Path(tempfile.mkdtemp())
    joblib.dump(model,     tmpdir / "best_model.pkl")
    joblib.dump(scaler,    tmpdir / "scaler.pkl")
    joblib.dump(features,  tmpdir / "features.pkl")
    joblib.dump(encoders,  tmpdir / "encoders.pkl")
    joblib.dump(0.5,       tmpdir / "threshold.pkl")
    with open(tmpdir / "shap_explainer.pkl", "wb") as f:
        pickle.dump(explainer, f)

    return tmpdir, features


@pytest.fixture(scope="module")
def loaded_model():
    tmpdir, features = _train_tiny_model()
    from services.ml_predictor import load_model, activate_model
    key = load_model(
        model_path=str(tmpdir / "best_model.pkl"),
        scaler_path=str(tmpdir / "scaler.pkl"),
        explainer_path=str(tmpdir / "shap_explainer.pkl"),
        features_path=str(tmpdir / "features.pkl"),
        encoders_path=str(tmpdir / "encoders.pkl"),
        threshold_path=str(tmpdir / "threshold.pkl"),
        model_version_id=9999,
    )
    activate_model(key)
    return features


class TestPredictor:
    def test_is_ready(self, loaded_model):
        from services.ml_predictor import is_ready
        assert is_ready()

    def test_predict_returns_dict(self, loaded_model):
        from services.ml_predictor import predict
        data   = {f: 0.5 for f in loaded_model}
        result = predict(data)
        assert isinstance(result, dict)

    def test_predict_has_required_keys(self, loaded_model):
        from services.ml_predictor import predict
        data   = {f: 0.5 for f in loaded_model}
        result = predict(data)
        for key in ["label", "risk_score", "risk_level", "probability", "ai_summary"]:
            assert key in result, f"Missing key: {key}"

    def test_risk_score_range(self, loaded_model):
        from services.ml_predictor import predict
        data   = {f: 0.5 for f in loaded_model}
        result = predict(data)
        assert 0 <= result["risk_score"] <= 100

    def test_label_valid(self, loaded_model):
        from services.ml_predictor import predict
        data   = {f: 0.5 for f in loaded_model}
        result = predict(data)
        assert result["label"] in ("SOLVABLE", "NON-SOLVABLE")

    def test_risk_level_valid(self, loaded_model):
        from services.ml_predictor import predict
        data   = {f: 0.5 for f in loaded_model}
        result = predict(data)
        assert result["risk_level"] in ("FAIBLE", "MOYEN", "ÉLEVÉ")

    def test_shap_factors_present(self, loaded_model):
        from services.ml_predictor import predict
        data   = {f: 0.5 for f in loaded_model}
        result = predict(data)
        assert isinstance(result["top_factors"], list)

    def test_predict_batch(self, loaded_model):
        from services.ml_predictor import predict_batch
        records = [{f: float(i) * 0.1 for f in loaded_model} for i in range(5)]
        results = predict_batch(records)
        assert len(results) == 5
        assert all("label" in r or "error" in r for r in results)

    def test_no_model_raises(self):
        """Without loading a model, calling predict should raise RuntimeError."""
        import services.ml_predictor as mp
        old_key = mp._active_key
        mp._active_key = None
        with pytest.raises(RuntimeError):
            mp.predict({"F0": 1})
        mp._active_key = old_key  # restore


class TestDrift:
    def test_compute_psi_identical(self):
        from services.ml_predictor import compute_psi
        a = np.random.default_rng(0).uniform(0, 1, 500)
        assert compute_psi(a, a) < 0.01

    def test_compute_psi_different(self):
        from services.ml_predictor import compute_psi
        a = np.zeros(200)
        b = np.ones(200)
        assert compute_psi(a, b) > 0.2

    def test_detect_drift_no_drift(self):
        from services.ml_predictor import detect_drift
        rng  = np.random.default_rng(1)
        feat = ["X1", "X2"]
        ref  = pd.DataFrame({"X1": rng.normal(0, 1, 300), "X2": rng.normal(5, 2, 300)})
        cur  = pd.DataFrame({"X1": rng.normal(0, 1, 300), "X2": rng.normal(5, 2, 300)})
        res  = detect_drift(ref, cur, feat)
        assert res["drift_detected"] is False

    def test_detect_drift_with_drift(self):
        from services.ml_predictor import detect_drift
        feat = ["X1"]
        ref  = pd.DataFrame({"X1": np.zeros(200)})
        cur  = pd.DataFrame({"X1": np.ones(200)})
        res  = detect_drift(ref, cur, feat, psi_threshold=0.1)
        assert res["drift_detected"] is True
