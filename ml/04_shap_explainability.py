# 04_shap_explainability.py

import os
import joblib
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import shap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
CHARTS_DIR = os.path.join(BASE_DIR, "data", "charts")
DATA_PATH = os.path.join(BASE_DIR, "data", "dataset_clean.csv")

os.makedirs(CHARTS_DIR, exist_ok=True)

# LOAD ARTIFACTS

FEATURES = joblib.load(os.path.join(MODELS_DIR, "features.pkl"))
NUMERIC_FEATURES = joblib.load(os.path.join(MODELS_DIR, "numeric_features.pkl"))
CATEGORICAL_FEATURES = joblib.load(os.path.join(MODELS_DIR, "categorical_features.pkl"))

model = joblib.load(os.path.join(MODELS_DIR, "model.pkl"))
best_threshold = joblib.load(os.path.join(MODELS_DIR, "best_threshold.pkl"))
explainer = joblib.load(os.path.join(MODELS_DIR, "shap_explainer.pkl"))

print("Artifacts chargés")
print(f"Modèle : {type(model).__name__}")


# ENCODAGE

def encode_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    encoders_path = os.path.join(MODELS_DIR, "label_encoders.pkl")

    df = df.copy()

    if os.path.exists(encoders_path):
        label_encoders = joblib.load(encoders_path)

        for col, le in label_encoders.items():
            if col in df.columns:
                df[col] = df[col].astype(str).apply(
                    lambda x: le.transform([x])[0] if x in le.classes_ else -1
                )

        return df

    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("category").cat.codes

    return df


# EXPLICATION CLIENT

def explain_client_original(client_data: dict) -> dict:
    df_input = pd.DataFrame([client_data])
    X_input = df_input.reindex(columns=FEATURES, fill_value=0)
    X_input = encode_dataframe(X_input)

    y_proba = float(model.predict_proba(X_input)[:, 1][0])
    pred = int(y_proba >= best_threshold)

    risk_score = int(round((1 - y_proba) * 100))

    if risk_score <= 30:
        risk_level = "FAIBLE"
        risk_color = "green"
    elif risk_score <= 60:
        risk_level = "MOYEN"
        risk_color = "orange"
    else:
        risk_level = "ÉLEVÉ"
        risk_color = "red"

    try:
        shap_vals = explainer.shap_values(X_input)

        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1]

        shap_vals = np.array(shap_vals)[0]

    except Exception as e:
        print(f"Erreur SHAP : {e}")
        shap_vals = np.zeros(len(FEATURES))

    factors = []

    for feat, sv in zip(FEATURES, shap_vals):
        value = X_input.iloc[0][feat]

        factors.append({
            "feature": feat,
            "value_original": float(value) if pd.notnull(value) else 0,
            "shap_value": float(sv),
            "impact": "positif" if sv > 0 else "negatif",
        })

    factors_sorted = sorted(
        factors,
        key=lambda x: abs(x["shap_value"]),
        reverse=True,
    )

    return {
        "prediction": pred,
        "label": "SOLVABLE" if pred == 1 else "NON-SOLVABLE",
        "probability": round(y_proba * 100, 2),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "top_factors": factors_sorted[:5],
        "all_factors": factors_sorted,
    }


# TEST CLIENT

print("\n" + "=" * 60)
print("EXPLICATION INDIVIDUELLE")
print("=" * 60)

df_test = pd.read_csv(DATA_PATH)
sample = df_test.iloc[0]

result = explain_client_original(sample.to_dict())

print(f"\nPrédiction : {result['label']}")
print(f"Probabilité : {result['probability']}%")
print(f"Risk Score : {result['risk_score']}/100 ({result['risk_level']})")

print("\nTop 5 facteurs :")

for f in result["top_factors"]:
    sign = "↑" if f["impact"] == "positif" else "↓"
    print(
        f"{sign} "
        f"{f['feature']:<30} "
        f"val={f['value_original']:>10.2f} "
        f"SHAP={f['shap_value']:>+10.4f}"
    )


# GLOBAL SHAP

print("\nGénération des graphiques SHAP...")

sample_size = min(200, len(df_test))

X_sample = df_test.reindex(columns=FEATURES, fill_value=0).iloc[:sample_size]
X_sample = encode_dataframe(X_sample)

try:
    shap_vals = explainer.shap_values(X_sample)

    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]

    shap_vals = np.array(shap_vals)

    # FIGURE SHAP PROPRE 

    feature_names_fr = {
        "NB_RETARDS": "Nombre de retards",
        "RETARD_PONDERE": "Retard pondéré",
        "RETARD_STD": "Stabilité des retards",
        "NB_MODES_PAIEMENT": "Modes de paiement",
        "NB_REGLEMENTS": "Nombre de règlements",
        "ANCIENNETE_CLIENT": "Ancienneté client",
        "MONTANT_MOY_REG": "Montant moyen réglé",
        "JOURS_DEPUIS_DERNIER_ACHAT": "Dernier achat",
        "FREQUENCE_ACHAT": "Fréquence d'achat",
        "TOTAL_MONTANT_REG": "Montant total réglé",
        "RATIO_PAIEMENT": "Ratio de paiement",
        "MONTANT_MAX_FACTURE": "Montant max facture",
        "NATURE_CLIENT": "Nature client",
        "GOUVERNORAT": "Gouvernorat",
        "TOTAL_MONTANT_TTC": "Montant total TTC",
        "NB_FACTURES": "Nombre de factures",
        "MONTANT_MOY_FACTURE": "Montant moyen facture",
        "PART_CA_CLIENT": "Part chiffre d'affaires",
    }

    mean_abs_shap = np.abs(shap_vals).mean(axis=0)

    importance_df = pd.DataFrame({
        "variable": FEATURES,
        "importance": mean_abs_shap,
    })

    importance_df["variable_fr"] = importance_df["variable"].map(
        lambda x: feature_names_fr.get(x, x)
    )

    importance_df = importance_df.sort_values(
        by="importance",
        ascending=False
    ).head(10)

    plt.figure(figsize=(10, 6))

    plt.barh(
        importance_df["variable_fr"][::-1],
        importance_df["importance"][::-1],
        color="#2E86DE"
    )

    plt.title(
        "Importance des variables dans la prédiction",
        fontsize=15,
        fontweight="bold"
    )

    plt.xlabel("Impact moyen sur la prédiction")
    plt.ylabel("")
    plt.grid(axis="x", linestyle="--", alpha=0.35)

    plt.tight_layout()

    plt.savefig(
        os.path.join(CHARTS_DIR, "shap_importance_report.png"),
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()



    X_sample_report = X_sample.copy()
    X_sample_report = X_sample_report.rename(columns=feature_names_fr)

    shap.summary_plot(
        shap_vals,
        X_sample_report,
        feature_names=X_sample_report.columns,
        show=False,
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(CHARTS_DIR, "shap_summary_report.png"),
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()

    print("Graphiques SHAP sauvegardés :")
    print("- shap_importance_report.png")
    print("- shap_summary_report.png")

except Exception as e:
    print(f"SHAP global échoué : {e}")

print("\n" + "=" * 60)
print("EXPLICATION TERMINÉE")
print("=" * 60)