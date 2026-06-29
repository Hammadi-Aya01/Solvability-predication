"""
services/preprocessing.py
Re-exports preprocessing pipeline from services/ml_preprocessing.py
(the actual heavy ML code lives there, adapted from the provided source).
"""
from services.ml_preprocessing import (
    validate_dataset,
    clean_and_engineer,
    encode_categoricals,
    prepare_features,
    REQUIRED_COLUMNS,
    TARGET_COLUMN,
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    ValidationReport,
)

__all__ = [
    "validate_dataset",
    "clean_and_engineer",
    "encode_categoricals",
    "prepare_features",
    "REQUIRED_COLUMNS",
    "TARGET_COLUMN",
    "CATEGORICAL_COLUMNS",
    "NUMERIC_COLUMNS",
    "ValidationReport",
]
