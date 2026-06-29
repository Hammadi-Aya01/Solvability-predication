"""
services/ml_predictor.py
FIXES:
  1. predict_proba() returns [prob_class_0, prob_class_1]
     class 0 = NON-SOLVABLE, class 1 = SOLVABLE (as trained)
     So: prob_non_solvable = proba_arr[0], prob_solvable = proba_arr[1]
     The original code had them SWAPPED — every solvable client showed
     as high risk and every non-solvable showed as low risk.
  2. risk_score = prob_non_solvable * 100 (high score = high risk) — unchanged
     but now uses the correct probability index
  3. label: prediction=1 when prob_non_solvable >= threshold (unchanged logic,
     but now actually means NON-SOLVABLE because we use correct index)
"""
from __future__ import annotations

import pickle
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

_lock = threading.RLock()
CAT_COLS = ["NATURE_CLIENT", "GOUVERNORAT"]


@dataclass
class LoadedModel:
    model:      Any
    scaler:     Any
    explainer:  Any
    features:   list[str]
    encoders:   dict
    threshold:  float = 0.5
    model_type: str   = "unknown"


_registry:   dict[str, LoadedModel] = {}
_active_key: str | None             = None


def load_model(model_path, scaler_path, explainer_path, features_path,
               encoders_path, threshold_path=None, model_version_id=None) -> str:
    key = str(model_version_id or Path(model_path).parent.name)
    with _lock:
        model    = joblib.load(model_path)
        scaler   = joblib.load(scaler_path)
        features = joblib.load(features_path)
        encoders = joblib.load(encoders_path)
        with open(explainer_path, "rb") as f:
            explainer = pickle.load(f)
        threshold = 0.5
        if threshold_path and Path(threshold_path).exists():
            threshold = float(joblib.load(threshold_path))
        _registry[key] = LoadedModel(
            model=model, scaler=scaler, explainer=explainer,
            features=features, encoders=encoders,
            threshold=threshold, model_type=type(model).__name__)
    return key


def activate_model(key: str) -> None:
    global _active_key
    if key not in _registry:
        raise ValueError(f"Model key '{key}' not in registry.")
    with _lock:
        _active_key = key


def get_active_model() -> LoadedModel | None:
    with _lock:
        if _active_key and _active_key in _registry:
            return _registry[_active_key]
    return None


def is_ready() -> bool:
    return get_active_model() is not None


def _encode_input(client_data: dict, features: list[str], encoders: dict) -> dict:
    out = {}
    for f in features:
        if f in CAT_COLS:
            val = client_data.get(f, "INCONNU")
            val = "INCONNU" if val is None else str(val)
            le  = encoders.get(f)
            if le is not None and val in le.classes_:
                out[f] = int(le.transform([val])[0])
            else:
                out[f] = -1
        else:
            v = client_data.get(f, 0)
            out[f] = float(v) if v is not None else 0.0
    return out


def _extract_shap_values(explainer, input_scaled: pd.DataFrame) -> np.ndarray:
    try:
        sv     = explainer(input_scaled)
        values = sv.values
        if values.ndim == 3:
            values = values[:, :, 1]
        return values[0]
    except Exception:
        shap_raw = explainer.shap_values(input_scaled)
        arr = np.array(shap_raw)
        if isinstance(shap_raw, list) and len(shap_raw) > 1:
            return np.array(shap_raw[1])[0]
        elif arr.ndim == 3:
            return arr[1, 0, :]
        else:
            return arr[0]


def predict(client_data: dict) -> dict:
    lm = get_active_model()
    if lm is None:
        raise RuntimeError("Aucun modèle actif.")

    with _lock:
        model, scaler      = lm.model, lm.scaler
        features, encoders = lm.features, lm.encoders
        threshold          = lm.threshold
        explainer          = lm.explainer

    encoded      = _encode_input(client_data, features, encoders)
    input_df     = pd.DataFrame([encoded], columns=features)
    input_scaled = pd.DataFrame(scaler.transform(input_df), columns=features)

    proba_arr = model.predict_proba(input_scaled)[0]

    # Model trained with CIBLE/SOLVABLE: 1=SOLVABLE, 0=NON-SOLVABLE.
    # predict_proba returns [prob_class_0, prob_class_1]
    # = [prob_non_solvable, prob_solvable].  The optimized threshold is
    # computed on prob_solvable, so the decision must use prob_solvable.
    prob_non_solvable = float(proba_arr[0])
    prob_solvable     = float(proba_arr[1])

    # High risk_score = higher risk (non-solvable).
    prediction = int(prob_solvable >= threshold)
    risk_score = int(round((1.0 - prob_solvable) * 100))

    if   risk_score <= 30: risk_level, risk_color = "FAIBLE", "green"
    elif risk_score <= 60: risk_level, risk_color = "MOYEN",  "orange"
    else:                  risk_level, risk_color = "ÉLEVÉ",  "red"

    factors: list[dict] = []
    try:
        shap_row = _extract_shap_values(explainer, input_scaled)
        factors = sorted([
            {"feature": feat, "shap_value": round(float(sv), 4),
             "feature_value": round(float(input_df[feat].iloc[0]), 4),
             "impact": "positif" if sv > 0 else "negatif"}
            for feat, sv in zip(features, shap_row)
        ], key=lambda x: abs(x["shap_value"]), reverse=True)
    except Exception:
        pass

    ai_summary = _generate_ai_summary(factors, risk_level, risk_score)

    similar_hint = None
    nb_f = client_data.get("NB_FACTURES", 0)
    if nb_f is not None and float(nb_f) < 3:
        similar_hint = {"message": "Client nouveau — score basé sur profil similaire",
                        "nb_factures": nb_f}

    return {
        "prediction":       prediction,
        "label":            "SOLVABLE" if prediction == 1 else "NON-SOLVABLE",
        "probability":      round(prob_solvable * 100, 2),
        "probability_risk": round(prob_non_solvable * 100, 2),
        "risk_score":       risk_score,
        "risk_level":       risk_level,
        "risk_color":       risk_color,
        "threshold_used":   threshold,
        "top_factors":      factors[:5],
        "all_factors":      factors,
        "ai_summary":       ai_summary,
        "similar_hint":     similar_hint,
        "retard_max":       client_data.get("RETARD_MAX", 0),
    }


def predict_batch(records: list[dict]) -> list[dict]:
    results = []
    for rec in records:
        try:
            r = predict(rec)
            r["code_client"] = rec.get("CODE_CLIENT", "")
            r["error"]       = None
        except Exception as e:
            r = {"code_client": rec.get("CODE_CLIENT", ""), "error": str(e)}
        results.append(r)
    return results


def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    eps = 1e-8
    bp  = np.linspace(0, 1, buckets + 1)
    ep  = np.histogram(expected, bins=bp)[0] / (len(expected) + eps)
    ap  = np.histogram(actual,   bins=bp)[0] / (len(actual)   + eps)
    ep  = np.where(ep == 0, eps, ep)
    ap  = np.where(ap == 0, eps, ap)
    return float(np.sum((ap - ep) * np.log(ap / ep)))


def detect_drift(reference_df, current_df, feature_names, psi_threshold=0.2) -> dict:
    drifted, psi_scores = [], {}
    for feat in feature_names:
        if feat not in reference_df.columns or feat not in current_df.columns:
            continue
        ref = reference_df[feat].dropna().values.astype(float)
        cur = current_df[feat].dropna().values.astype(float)
        if not len(ref) or not len(cur):
            continue
        combined = np.concatenate([ref, cur])
        mn, mx   = combined.min(), combined.max()
        if mx == mn:
            continue
        psi = compute_psi((ref - mn) / (mx - mn), (cur - mn) / (mx - mn))
        psi_scores[feat] = round(psi, 4)
        if psi > psi_threshold:
            drifted.append(feat)
    overall = round(np.mean(list(psi_scores.values())) if psi_scores else 0.0, 4)
    return {"drift_detected": len(drifted) > 0, "overall_psi": overall,
            "features_drifted": drifted, "psi_by_feature": psi_scores,
            "threshold": psi_threshold}


_FEATURE_LABELS = {
    "RETARD_PONDERE": "retard pondéré", "NB_RETARDS": "nombre de retards",
    "RATIO_PAIEMENT": "ratio de paiement", "TAUX_RETARD": "taux de retard",
    "ANCIENNETE_CLIENT": "ancienneté client", "TOTAL_MONTANT_TTC": "chiffre d'affaires total",
    "NB_FACTURES": "nombre de factures", "FREQUENCE_ACHAT": "fréquence d'achat",
    "JOURS_DEPUIS_DERNIER_ACHAT": "inactivité récente",
    "TOTAL_MONTANT_REG": "montant total réglé", "NB_REGLEMENTS": "nombre de règlements",
    "NB_MODES_PAIEMENT": "modes de paiement utilisés", "PART_CA_CLIENT": "part du CA client",
    "MONTANT_MOY_FACTURE": "montant moyen par facture", "RETARD_STD": "stabilité des retards",
    "TOTAL_IMPAYE": "montant impayé total", "RETARD_MAX": "retard maximum observé",
}


def _label(feat: str) -> str:
    return _FEATURE_LABELS.get(feat, feat.replace("_", " ").lower())


def _generate_ai_summary(factors, risk_level, risk_score) -> str:
    if not factors:
        return "Aucune donnée SHAP disponible pour ce client."
    pos = [f for f in factors[:5] if f["impact"] == "positif"]
    neg = [f for f in factors[:5] if f["impact"] == "negatif"]
    level_text = {
        "FAIBLE": f"Ce client présente un profil de risque faible (score {risk_score}/100).",
        "MOYEN":  f"Ce client présente un profil de risque modéré (score {risk_score}/100).",
        "ÉLEVÉ":  f"Ce client présente un profil de risque élevé (score {risk_score}/100).",
    }.get(risk_level, f"Score de risque : {risk_score}/100.")
    parts = [level_text]
    if pos:
        parts.append(f"Facteurs aggravants : {', '.join(_label(f['feature']) for f in pos[:3])}.")
    if neg:
        parts.append(f"Facteurs atténuants : {', '.join(_label(f['feature']) for f in neg[:3])}.")
    if risk_score >= 70:
        parts.append("Une vérification approfondie est recommandée.")
    elif risk_score >= 40:
        parts.append("Un suivi régulier est conseillé.")
    return " ".join(parts)