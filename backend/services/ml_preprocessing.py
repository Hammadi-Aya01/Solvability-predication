"""
services/ml_preprocessing.py
Dataset validation, cleaning, and feature engineering pipeline.

FIX: encode_categoricals handles unknown categories → -1
     (consistent with ml_service.py and ml_predictor.py).
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

REQUIRED_COLUMNS = [
    "CODE_CLIENT", "NB_FACTURES", "TOTAL_MONTANT_TTC",
    "TOTAL_MONTANT_REG", "NB_REGLEMENTS", "RETARD_PONDERE", "NB_RETARDS",
]

TARGET_COLUMN       = "CIBLE"
CATEGORICAL_COLUMNS = ["NATURE_CLIENT", "GOUVERNORAT"]
NUMERIC_COLUMNS     = [
    # Core columns from the ML txt (ml_last_version.txt NUMERIC_FEATURES)
    "NB_FACTURES", "TOTAL_MONTANT_TTC", "TOTAL_MONTANT_REG",
    "NB_REGLEMENTS", "RETARD_PONDERE", "NB_RETARDS",
    "MONTANT_MOY_FACTURE", "MONTANT_MAX_FACTURE",
    "MONTANT_MOY_REG",
    "FREQUENCE_ACHAT", "ANCIENNETE_CLIENT", "JOURS_DEPUIS_DERNIER_ACHAT",
    "RETARD_STD", "NB_MODES_PAIEMENT",
    # Engineered features
    "RATIO_PAIEMENT", "TAUX_RETARD", "TOTAL_IMPAYE", "PART_CA_CLIENT",
    # Optional (may be present in some datasets)
    "RETARD_MAX",
]


class ValidationReport:
    def __init__(self):
        self.errors: list[str]     = []
        self.warnings: list[str]   = []
        self.stats: dict[str, Any] = {}

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {"is_valid": self.is_valid, "errors": self.errors,
                "warnings": self.warnings, "stats": self.stats}


def validate_dataset(df: pd.DataFrame, require_target: bool = True) -> ValidationReport:
    report = ValidationReport()
    report.stats["nb_rows"] = len(df)
    report.stats["nb_cols"] = len(df.columns)

    if len(df) < 50:
        report.errors.append(f"Trop peu de lignes ({len(df)}). Minimum requis : 50.")

    normalised = {_normalise_col(c): c for c in df.columns}
    norm_cols  = set(normalised.keys())
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in norm_cols]
    if missing_cols:
        report.errors.append(f"Colonnes manquantes : {missing_cols}")

    if require_target:
        target_found = None
        for col in ["CIBLE", "SOLVABLE"]:
            if col in norm_cols:
                target_found = col
                break

        if not target_found:
            report.errors.append(
                "Colonne cible 'CIBLE' ou 'SOLVABLE' absente. "
                "Elle doit contenir 1 (solvable) ou 0 (non-solvable)."
            )
        else:
            real_col   = normalised[target_found]
            unique_vals = df[real_col].dropna().unique().tolist()
            if not set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                report.errors.append(
                    f"Colonne '{target_found}' contient des valeurs invalides : {unique_vals}."
                )
            else:
                counts = df[real_col].value_counts().to_dict()
                report.stats["target_distribution"] = {str(int(k)): int(v) for k, v in counts.items()}
                if 0 in counts and 1 in counts:
                    ratio = min(counts[0], counts[1]) / max(counts[0], counts[1])
                    if ratio < 0.05:
                        report.warnings.append(
                            f"Déséquilibre classes très fort (ratio={ratio:.2f}). SMOTE sera appliqué."
                        )

    missing_pct  = (df.isnull().sum() / len(df) * 100).round(2)
    high_missing = missing_pct[missing_pct > 50].to_dict()
    if high_missing:
        report.warnings.append(f"Colonnes avec >50% valeurs manquantes : {high_missing}.")
    report.stats["missing_pct_top5"] = missing_pct.nlargest(5).to_dict()

    if "CODE_CLIENT" in df.columns:
        n_dupes = df.duplicated(subset=["CODE_CLIENT"]).sum()
        if n_dupes > 0:
            report.warnings.append(f"{n_dupes} CODE_CLIENT dupliqués détectés.")
        report.stats["duplicate_code_clients"] = int(n_dupes)

    return report


def clean_and_engineer(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalise_col(c) for c in df.columns]

    if "SOLVABLE" in df.columns and "CIBLE" not in df.columns:
        df = df.rename(columns={"SOLVABLE": "CIBLE"})

    if "CODE_CLIENT" in df.columns:
        df = df.drop_duplicates(subset=["CODE_CLIENT"], keep="first")

    thresh = int(0.5 * len(df))
    df = df.dropna(thresh=thresh, axis=1)

    num_cols = df.select_dtypes(include=[np.number]).columns
    for c in num_cols:
        if c != TARGET_COLUMN:
            df[c] = df[c].fillna(df[c].median())

    cat_cols = df.select_dtypes(include=["object"]).columns
    for c in cat_cols:
        mode = df[c].mode()
        df[c] = df[c].fillna(mode[0] if len(mode) else "INCONNU")

    df = _engineer_features(df)

    for c in df.select_dtypes(include=[np.number]).columns:
        if c == TARGET_COLUMN:
            continue
        q1, q3 = df[c].quantile(0.01), df[c].quantile(0.99)
        df[c] = df[c].clip(q1, q3)

    return df


def _normalise_col(name: str) -> str:
    name = str(name).strip().upper()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^A-Z0-9_]", "", name)
    return name


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    if "TOTAL_MONTANT_TTC" in df.columns and "TOTAL_MONTANT_REG" in df.columns:
        df["RATIO_PAIEMENT"] = (
            df["TOTAL_MONTANT_REG"] / df["TOTAL_MONTANT_TTC"].replace(0, np.nan)
        ).fillna(0).clip(0, 1)

    if "NB_RETARDS" in df.columns and "NB_FACTURES" in df.columns:
        df["TAUX_RETARD"] = (
            df["NB_RETARDS"] / df["NB_FACTURES"].replace(0, np.nan)
        ).fillna(0).clip(0, 1)

    if "TOTAL_MONTANT_TTC" in df.columns and "NB_FACTURES" in df.columns:
        df["MONTANT_MOY_FACTURE"] = (
            df["TOTAL_MONTANT_TTC"] / df["NB_FACTURES"].replace(0, np.nan)
        ).fillna(0)
        # MONTANT_MAX_FACTURE: if not present, estimate as MOY × 2 (conservative)
        if "MONTANT_MAX_FACTURE" not in df.columns:
            df["MONTANT_MAX_FACTURE"] = df["MONTANT_MOY_FACTURE"] * 2.0

    if "TOTAL_MONTANT_REG" in df.columns and "NB_REGLEMENTS" in df.columns:
        df["MONTANT_MOY_REG"] = (
            df["TOTAL_MONTANT_REG"] / df["NB_REGLEMENTS"].replace(0, np.nan)
        ).fillna(0)

    if "TOTAL_MONTANT_TTC" in df.columns and "TOTAL_MONTANT_REG" in df.columns:
        df["TOTAL_IMPAYE"] = (df["TOTAL_MONTANT_TTC"] - df["TOTAL_MONTANT_REG"]).clip(0)

    if "TOTAL_MONTANT_TTC" in df.columns:
        total = df["TOTAL_MONTANT_TTC"].sum()
        df["PART_CA_CLIENT"] = (
            df["TOTAL_MONTANT_TTC"] / total * 100 if total > 0 else 0.0
        )
    return df


def encode_categoricals(
    df: pd.DataFrame,
    fit: bool = True,
    encoders: dict[str, LabelEncoder] | None = None,
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """
    Label-encode categorical columns.
    FIX: unknown categories during inference → -1 (consistent with ml_service.py).
    """
    df = df.copy()
    if encoders is None:
        encoders = {}

    cols = [c for c in CATEGORICAL_COLUMNS if c in df.columns]

    for col in cols:
        if fit:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        else:
            le = encoders.get(col)
            if le is None:
                df[col] = -1
            else:
                df[col] = df[col].astype(str).apply(
                    lambda v: int(le.transform([v])[0]) if v in le.classes_ else -1
                )

    return df, encoders


def prepare_features(
    df: pd.DataFrame,
    feature_names: list[str],
    encoders: dict[str, LabelEncoder],
) -> pd.DataFrame:
    """Prepare a DataFrame for inference: encode then align to training feature list."""
    df, _ = encode_categoricals(df, fit=False, encoders=encoders)
    return df.reindex(columns=feature_names, fill_value=0)
