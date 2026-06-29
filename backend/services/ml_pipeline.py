"""
services/ml_pipeline.py
FIXES:
  1. use_label_encoder=False removed from XGBoost (dropped in XGBoost >= 1.6)
  2. Threshold search floor raised to 0.4 (not 0.3) — prevents over-aggressive
     non-solvable classification that made 99% of clients show as high risk
  3. artifact_paths key is "shap_explainer" so PredictionService finds it
"""
from __future__ import annotations
import json, pickle, warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib, numpy as np, optuna, pandas as pd, shap
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                              recall_score, roc_auc_score)
from sklearn.model_selection import (StratifiedKFold, cross_val_score,
                                     train_test_split)
from sklearn.preprocessing import StandardScaler

from services.ml_preprocessing import (TARGET_COLUMN, CATEGORICAL_COLUMNS,
    clean_and_engineer, encode_categoricals, validate_dataset)

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class ModelResult:
    name: str; model: Any; scaler: StandardScaler
    metrics: dict; feature_names: list; encoders: dict; best_threshold: float = 0.5


@dataclass
class TrainingReport:
    success: bool; best_model_name: str = ""
    results: list = field(default_factory=list)
    artifact_paths: dict = field(default_factory=dict)
    error: str = ""; feature_importances: dict = field(default_factory=dict)

    def to_dict(self):
        return {"success": self.success, "best_model_name": self.best_model_name,
                "results": self.results, "artifact_paths": self.artifact_paths,
                "error": self.error, "feature_importances": self.feature_importances}


def run_training_pipeline(df_raw, output_dir, n_trials=20, progress_callback=None):
    def _p(s, p):
        if progress_callback: progress_callback(s, p)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        _p("Validation du dataset", 5)
        rpt = validate_dataset(df_raw, require_target=True)
        if not rpt.is_valid:
            return TrainingReport(success=False, error="; ".join(rpt.errors))

        _p("Nettoyage et feature engineering", 10)
        df = clean_and_engineer(df_raw)

        _p("Encodage", 15)
        df, encoders = encode_categoricals(df, fit=True)

        drop = [TARGET_COLUMN, "SOLVABLE", "CODE_CLIENT"]
        fcols = [c for c in df.columns if c not in drop
                 and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, int, float]]

        X = df[fcols].values
        y = df[TARGET_COLUMN].astype(int).values
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                                    random_state=42, stratify=y)

        _p("SMOTE", 20)
        try:
            sm = SMOTE(random_state=42, k_neighbors=min(5, np.bincount(y_tr).min() - 1))
            X_tr, y_tr = sm.fit_resample(X_tr, y_tr)
        except Exception:
            pass

        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)
        X_te_s = sc.transform(X_te)

        results = []
        _p("Entraînement Régression Logistique", 30)
        results.append(_logistic(X_tr_s, y_tr, X_te_s, y_te, fcols, sc, encoders))
        _p("Entraînement RandomForest", 50)
        results.append(_rf(X_tr_s, y_tr, X_te_s, y_te, fcols, sc, encoders, n_trials))
        _p("Entraînement XGBoost", 70)
        results.append(_xgb(X_tr_s, y_tr, X_te_s, y_te, fcols, sc, encoders, n_trials))

        _p("Sélection meilleur modèle", 80)
        best = max(results, key=lambda r: r.metrics.get("f1", 0))

        _p("Sauvegarde artefacts", 85)
        paths = _save(best, output_dir, fcols, encoders)

        _p("SHAP", 90)
        sp = _shap(best.model, X_te_s[:200], output_dir)
        paths["shap_explainer"] = str(sp)   # FIX 3: correct key name

        fi = _fi(best.model, fcols)
        _p("Terminé", 100)

        return TrainingReport(
            success=True, best_model_name=best.name,
            results=[{"name": r.name, "metrics": r.metrics} for r in results],
            artifact_paths=paths, feature_importances=fi)

    except Exception as ex:
        return TrainingReport(success=False, error=str(ex))


def _evaluate(model, X, y):
    proba = model.predict_proba(X)[:, 1]
    # FIX 2: floor at 0.4 — prevents threshold=0.3 which labels 99% as non-solvable
    bt, bf = 0.5, 0.0
    for t in np.arange(0.4, 0.8, 0.02):
        p = (proba >= t).astype(int)
        f = f1_score(y, p, zero_division=0)
        if f > bf:
            bf, bt = f, t
    yp = (proba >= bt).astype(int)
    return {
        "accuracy":  round(accuracy_score(y, yp), 4),
        "precision": round(precision_score(y, yp, zero_division=0), 4),
        "recall":    round(recall_score(y, yp, zero_division=0), 4),
        "f1":        round(f1_score(y, yp, zero_division=0), 4),
        "roc_auc":   round(roc_auc_score(y, proba), 4),
        "threshold": round(bt, 2),
    }, bt


def _logistic(X_tr, y_tr, X_te, y_te, fcols, sc, enc):
    """Régression Logistique — modèle de base décrit dans le rapport PFE."""
    m = LogisticRegression(max_iter=2000, random_state=42, class_weight="balanced")
    m.fit(X_tr, y_tr)
    met, thr = _evaluate(m, X_te, y_te)
    return ModelResult("RegressionLogistique", m, sc, met, fcols, enc, thr)


def _rf(X_tr, y_tr, X_te, y_te, fcols, sc, enc, n_trials):
    def obj(t):
        p = {"n_estimators": t.suggest_int("n_estimators", 50, 300),
             "max_depth": t.suggest_int("max_depth", 3, 15),
             "min_samples_split": t.suggest_int("min_samples_split", 2, 20),
             "min_samples_leaf": t.suggest_int("min_samples_leaf", 1, 10),
             "max_features": t.suggest_categorical("max_features", ["sqrt", "log2"]),
             "class_weight": "balanced", "random_state": 42, "n_jobs": -1}
        return cross_val_score(RandomForestClassifier(**p), X_tr, y_tr,
               cv=StratifiedKFold(3, shuffle=True, random_state=42),
               scoring="roc_auc").mean()
    s = optuna.create_study(direction="maximize")
    s.optimize(obj, n_trials=n_trials, show_progress_bar=False)
    m = RandomForestClassifier(**{**s.best_params, "class_weight": "balanced",
                                   "random_state": 42, "n_jobs": -1})
    m.fit(X_tr, y_tr)
    met, thr = _evaluate(m, X_te, y_te)
    return ModelResult("RandomForest", m, sc, met, fcols, enc, thr)


def _xgb(X_tr, y_tr, X_te, y_te, fcols, sc, enc, n_trials):
    try:
        from xgboost import XGBClassifier
    except ImportError:
        return _dummy("XGBoost", X_te, y_te, fcols, sc, enc)
    sp = (y_tr == 0).sum() / max(1, (y_tr == 1).sum())

    def obj(t):
        # FIX 1: no use_label_encoder param (removed in XGBoost >= 1.6)
        p = {"n_estimators": t.suggest_int("n_estimators", 50, 400),
             "max_depth": t.suggest_int("max_depth", 3, 10),
             "learning_rate": t.suggest_float("learning_rate", 0.01, 0.3, log=True),
             "subsample": t.suggest_float("subsample", 0.5, 1.0),
             "colsample_bytree": t.suggest_float("colsample_bytree", 0.5, 1.0),
             "reg_alpha": t.suggest_float("reg_alpha", 0, 5),
             "reg_lambda": t.suggest_float("reg_lambda", 1, 10),
             "scale_pos_weight": sp, "eval_metric": "logloss",
             "random_state": 42, "n_jobs": -1}
        return cross_val_score(XGBClassifier(**p), X_tr, y_tr,
               cv=StratifiedKFold(3, shuffle=True, random_state=42),
               scoring="roc_auc").mean()
    s = optuna.create_study(direction="maximize")
    s.optimize(obj, n_trials=n_trials)
    m = XGBClassifier(**{**s.best_params, "scale_pos_weight": sp,
                          "eval_metric": "logloss", "random_state": 42, "n_jobs": -1})
    m.fit(X_tr, y_tr)
    met, thr = _evaluate(m, X_te, y_te)
    return ModelResult("XGBoost", m, sc, met, fcols, enc, thr)


def _lgbm(X_tr, y_tr, X_te, y_te, fcols, sc, enc, n_trials):
    try:
        from lightgbm import LGBMClassifier
    except ImportError:
        return _dummy("LightGBM", X_te, y_te, fcols, sc, enc)
    sp = (y_tr == 0).sum() / max(1, (y_tr == 1).sum())

    def obj(t):
        p = {"n_estimators": t.suggest_int("n_estimators", 50, 400),
             "max_depth": t.suggest_int("max_depth", 3, 12),
             "learning_rate": t.suggest_float("learning_rate", 0.01, 0.3, log=True),
             "num_leaves": t.suggest_int("num_leaves", 20, 150),
             "subsample": t.suggest_float("subsample", 0.5, 1.0),
             "colsample_bytree": t.suggest_float("colsample_bytree", 0.5, 1.0),
             "scale_pos_weight": sp, "random_state": 42, "n_jobs": -1, "verbose": -1}
        return cross_val_score(LGBMClassifier(**p), X_tr, y_tr,
               cv=StratifiedKFold(3, shuffle=True, random_state=42),
               scoring="roc_auc").mean()
    s = optuna.create_study(direction="maximize")
    s.optimize(obj, n_trials=n_trials)
    m = LGBMClassifier(**{**s.best_params, "scale_pos_weight": sp,
                           "random_state": 42, "n_jobs": -1, "verbose": -1})
    m.fit(X_tr, y_tr)
    met, thr = _evaluate(m, X_te, y_te)
    return ModelResult("LightGBM", m, sc, met, fcols, enc, thr)


def _dummy(name, X, y, fcols, sc, enc):
    from sklearn.dummy import DummyClassifier
    d = DummyClassifier(); d.fit(X, y)
    return ModelResult(name, d, sc, {"accuracy": 0, "precision": 0, "recall": 0,
                                      "f1": 0, "roc_auc": 0, "threshold": 0.5}, fcols, enc)


def _save(r, od, fcols, enc):
    p = {}
    joblib.dump(r.model,          od / "best_model.pkl"); p["model"]     = str(od / "best_model.pkl")
    joblib.dump(r.scaler,         od / "scaler.pkl");     p["scaler"]    = str(od / "scaler.pkl")
    joblib.dump(fcols,            od / "features.pkl");   p["features"]  = str(od / "features.pkl")
    joblib.dump(enc,              od / "encoders.pkl");   p["encoders"]  = str(od / "encoders.pkl")
    joblib.dump(r.best_threshold, od / "threshold.pkl");  p["threshold"] = str(od / "threshold.pkl")
    with open(od / "meta.json", "w") as f:
        json.dump({"model_type": r.name, "metrics": r.metrics,
                   "feature_names": fcols, "best_threshold": r.best_threshold}, f, indent=2)
    p["meta"] = str(od / "meta.json")
    return p


def _shap(model, X, od):
    try:
        ex = shap.TreeExplainer(model)
    except Exception:
        ex = shap.KernelExplainer(model.predict_proba, X[:50])
    path = od / "shap_explainer.pkl"
    with open(path, "wb") as f:
        pickle.dump(ex, f)
    return path


def _fi(model, fcols):
    try:
        return {k: round(float(v), 6) for k, v in zip(fcols, model.feature_importances_)}
    except AttributeError:
        return {}