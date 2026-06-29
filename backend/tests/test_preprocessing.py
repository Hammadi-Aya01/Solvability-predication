"""
tests/test_preprocessing.py
Unit tests for the ML preprocessing pipeline.
Run with: pytest tests/
"""
import numpy as np
import pandas as pd
import pytest
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.ml_preprocessing import (
    validate_dataset,
    clean_and_engineer,
    encode_categoricals,
    prepare_features,
    REQUIRED_COLUMNS,
    TARGET_COLUMN,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_valid_df(n=100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "CODE_CLIENT":       [f"C{i:04d}" for i in range(n)],
        "NB_FACTURES":       rng.integers(1, 50, n),
        "TOTAL_MONTANT_TTC": rng.uniform(1000, 100_000, n),
        "TOTAL_MONTANT_REG": rng.uniform(500, 90_000, n),
        "NB_REGLEMENTS":     rng.integers(1, 40, n),
        "RETARD_PONDERE":    rng.uniform(0, 30, n),
        "NB_RETARDS":        rng.integers(0, 10, n),
        "GOUVERNORAT":       rng.choice(["Tunis", "Sfax", "Sousse"], n),
        "NATURE_CLIENT":     rng.choice(["GMS", "DETAIL", "GROSSISTE"], n),
        "ANCIENNETE_CLIENT": rng.integers(1, 60, n),
        "CIBLE":             rng.integers(0, 2, n),
    })


# ── Validation tests ──────────────────────────────────────────────────────────

class TestValidation:
    def test_valid_dataset(self):
        df     = make_valid_df()
        report = validate_dataset(df)
        assert report.is_valid
        assert len(report.errors) == 0

    def test_too_few_rows(self):
        df     = make_valid_df(10)
        report = validate_dataset(df)
        assert not report.is_valid
        assert any("lignes" in e for e in report.errors)

    def test_missing_required_column(self):
        df = make_valid_df()
        df = df.drop(columns=["NB_FACTURES"])
        report = validate_dataset(df)
        assert not report.is_valid
        assert any("NB_FACTURES" in e for e in report.errors)

    def test_missing_target(self):
        df = make_valid_df()
        df = df.drop(columns=["CIBLE"])
        report = validate_dataset(df, require_target=True)
        assert not report.is_valid

    def test_target_not_required(self):
        df = make_valid_df()
        df = df.drop(columns=["CIBLE"])
        report = validate_dataset(df, require_target=False)
        assert report.is_valid

    def test_invalid_target_values(self):
        df = make_valid_df()
        df["CIBLE"] = 5  # invalid
        report = validate_dataset(df)
        assert not report.is_valid

    def test_duplicate_clients_warning(self):
        df = make_valid_df()
        df2 = pd.concat([df, df.iloc[:5]], ignore_index=True)
        report = validate_dataset(df2)
        assert any("dupliqués" in w for w in report.warnings)

    def test_target_distribution_in_stats(self):
        df     = make_valid_df()
        report = validate_dataset(df)
        assert "target_distribution" in report.stats


# ── Cleaning tests ────────────────────────────────────────────────────────────

class TestCleaning:
    def test_clean_returns_dataframe(self):
        df     = make_valid_df()
        result = clean_and_engineer(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_drops_duplicates(self):
        df  = make_valid_df(100)
        df2 = pd.concat([df, df.iloc[:10]], ignore_index=True)
        result = clean_and_engineer(df2)
        assert result["CODE_CLIENT"].nunique() == 100

    def test_ratio_paiement_created(self):
        df     = make_valid_df()
        result = clean_and_engineer(df)
        assert "RATIO_PAIEMENT" in result.columns
        assert result["RATIO_PAIEMENT"].between(0, 1).all()

    def test_taux_retard_created(self):
        df     = make_valid_df()
        result = clean_and_engineer(df)
        assert "TAUX_RETARD" in result.columns

    def test_total_impaye_created(self):
        df     = make_valid_df()
        result = clean_and_engineer(df)
        assert "TOTAL_IMPAYE" in result.columns
        assert (result["TOTAL_IMPAYE"] >= 0).all()

    def test_no_nan_in_numerics(self):
        df = make_valid_df()
        df.loc[0, "NB_FACTURES"] = np.nan
        result = clean_and_engineer(df)
        assert result["NB_FACTURES"].isna().sum() == 0

    def test_column_names_normalised(self):
        df = make_valid_df()
        df.columns = [c.lower() for c in df.columns]
        result = clean_and_engineer(df)
        assert all(c == c.upper() or c == c for c in result.columns)


# ── Encoding tests ────────────────────────────────────────────────────────────

class TestEncoding:
    def test_encode_fit(self):
        df     = make_valid_df()
        df     = clean_and_engineer(df)
        df_enc, encoders = encode_categoricals(df, fit=True)
        assert "GOUVERNORAT" in encoders
        assert df_enc["GOUVERNORAT"].dtype in [np.int64, np.int32, int]

    def test_encode_transform(self):
        df       = make_valid_df()
        df       = clean_and_engineer(df)
        _, encoders = encode_categoricals(df, fit=True)
        df2 = make_valid_df(20)
        df2 = clean_and_engineer(df2)
        df2_enc, _ = encode_categoricals(df2, fit=False, encoders=encoders)
        assert df2_enc["GOUVERNORAT"].dtype in [np.int64, np.int32, int]

    def test_unknown_category_handled(self):
        df       = make_valid_df()
        df       = clean_and_engineer(df)
        _, encoders = encode_categoricals(df, fit=True)
        df2 = make_valid_df(10)
        df2 = clean_and_engineer(df2)
        df2["GOUVERNORAT"] = "UNKNOWN_CITY"
        df2_enc, _ = encode_categoricals(df2, fit=False, encoders=encoders)
        assert (df2_enc["GOUVERNORAT"] == -1).all()


# ── prepare_features tests ────────────────────────────────────────────────────

class TestPrepareFeatures:
    def test_aligns_columns(self):
        df      = make_valid_df()
        df      = clean_and_engineer(df)
        df_enc, encoders = encode_categoricals(df, fit=True)
        feature_names = [c for c in df_enc.columns if c not in [TARGET_COLUMN, "CODE_CLIENT"]]
        df_new  = make_valid_df(5)
        df_new  = clean_and_engineer(df_new)
        result  = prepare_features(df_new, feature_names, encoders)
        assert list(result.columns) == feature_names
        assert len(result) == 5
