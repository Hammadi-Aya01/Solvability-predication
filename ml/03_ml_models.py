# 03_ml_models.py
import os
import warnings
import pickle
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import shap

from sklearn.model_selection    import train_test_split
from sklearn.preprocessing      import StandardScaler, LabelEncoder
from sklearn.metrics            import (
    f1_score, roc_auc_score, roc_curve,
    accuracy_score, precision_score, recall_score,
    confusion_matrix, classification_report,
    average_precision_score,
)
from sklearn.linear_model       import LogisticRegression
from sklearn.ensemble           import RandomForestClassifier
from xgboost                    import XGBClassifier
from imblearn.over_sampling     import SMOTE

warnings.filterwarnings("ignore")

# Chemins
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
DATA_PATH  = os.path.join(DATA_DIR, "dataset_clean.csv")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# Features (sans leakage)
NUMERIC_FEATURES = [
    "TOTAL_MONTANT_TTC", "NB_FACTURES", "MONTANT_MOY_FACTURE", "MONTANT_MAX_FACTURE",
    "FREQUENCE_ACHAT", "ANCIENNETE_CLIENT", "JOURS_DEPUIS_DERNIER_ACHAT",
    "TOTAL_MONTANT_REG", "NB_REGLEMENTS", "MONTANT_MOY_REG",
    "RETARD_STD", "RETARD_PONDERE",
    "NB_RETARDS", "NB_MODES_PAIEMENT",
    "RATIO_PAIEMENT", "PART_CA_CLIENT",
]

CATEGORICAL_FEATURES = ["NATURE_CLIENT", "GOUVERNORAT"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES


# Prétretement manuel 
#X_train_raw : features assliyaa 
def preprocess(X_train_raw, X_test_raw=None):
    X_train = X_train_raw.copy()
    X_test  = X_test_raw.copy() if X_test_raw is not None else None

    encoders = {}

    # LabelEncoder pour chaque colonne catégorielle
    for col in CATEGORICAL_FEATURES:
        le = LabelEncoder()
        X_train[col] = le.fit_transform(X_train[col].astype(str))
        if X_test is not None:
            # Valeurs inconnues → classe 0 (fallback)
            X_test[col] = X_test[col].astype(str).map(
                lambda v, le=le: le.transform([v])[0]
                if v in le.classes_ else 0
            )
        encoders[col] = le

    # Ordre des colonnes garanti
    feature_names = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    #After encoding 
    X_train_arr = X_train[feature_names].values.astype(float)
    X_test_arr  = X_test[feature_names].values.astype(float) if X_test is not None else None

    # StandardScaler sur toutes les colonnes
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_arr)
    X_test_scaled  = scaler.transform(X_test_arr) if X_test_arr is not None else None

    return X_train_scaled, X_test_scaled, scaler, encoders, feature_names

"""Dataset original
        ↓
Train/Test Split
        ↓
X_train_raw / X_test_raw
        ↓
Encoding catégories
        ↓
X_train_arr / X_test_arr
        ↓
Scaling
        ↓
X_train_scaled / X_test_scaled
        ↓
Model Training"""

# OPTIMISATION DU SEUIL (Youden's J)
# A l'aide de la courbe ROC et du critère de Youden 
def optimize_threshold(y_true, y_proba):
    #ROC Curve
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    return float(thresholds[best_idx]), float(j_scores[best_idx])


# PIPELINE PRINCIPAL

def run_training(data_path=None):
    path = data_path or DATA_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset non trouvé : {path}")

    df = pd.read_csv(path)

    print("=" * 60)
    print("TRAINING PIPELINE")
    print("=" * 60)

    # Validation colonnes
    missing = [f for f in ALL_FEATURES + ["SOLVABLE"] if f not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le dataset : {missing}")

    df = df.dropna(subset=["SOLVABLE"]).copy()

    X_raw = df[ALL_FEATURES]
    y     = df["SOLVABLE"].astype(int)

    print(f"Dataset : {len(df)} clients | "
          f"Solvables : {y.sum()} | Non-solvables : {(y==0).sum()}")

    # Split stratifié
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, random_state=42, stratify=y
    )

    # prétraitement AVANT SMOTE 
    # On encode + scale d'abord, puis on applique SMOTE sur les arrays résultants.
    print("\nPrétraitement (encodage + scaling)...")
    X_train_scaled, X_test_scaled, scaler, encoders, feature_names = preprocess(
        X_train_raw, X_test_raw
    )

    print(f"Train : {X_train_scaled.shape} | Test : {X_test_scaled.shape}")
    print(f"Classe 0 avant SMOTE : {(y_train == 0).sum()} | "
          f"Classe 1 avant SMOTE : {(y_train == 1).sum()}")

    # SMOTE sur données numériques pures
    smote = SMOTE(random_state=42, k_neighbors=min(5, (y_train == 0).sum() - 1))
    X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)

    print(f"Classe 0 après SMOTE : {(y_train_res == 0).sum()} | "
          f"Classe 1 après SMOTE : {(y_train_res == 1).sum()}")

    # Définition des modèles 
    models = {
        "Logistic": LogisticRegression(
            max_iter=2000, random_state=42, class_weight="balanced"
        ),
        "RF": RandomForestClassifier(
            n_estimators=250, random_state=42, n_jobs=-1, class_weight="balanced"
        ),
        "XGB": XGBClassifier(
            n_estimators=250, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            eval_metric="logloss", random_state=42,
            scale_pos_weight=(y_train_res == 0).sum() / max((y_train_res == 1).sum(), 1),
        ),
    }

    results = {}

    # Entraînement + évaluation
    for name, clf in models.items():
        print(f"\n  Entraînement {name}...")
        clf.fit(X_train_res, y_train_res)

        y_pred  = clf.predict(X_test_scaled)
        y_proba = clf.predict_proba(X_test_scaled)[:, 1]

        best_thr, youden = optimize_threshold(y_test, y_proba)
        y_pred_opt = (y_proba >= best_thr).astype(int)

        results[name] = {
            "clf":           clf,
            "f1_default":    f1_score(y_test, y_pred,     zero_division=0),
            "f1_optimized":  f1_score(y_test, y_pred_opt, zero_division=0),
            "auc":           roc_auc_score(y_test, y_proba),
            "ap":            average_precision_score(y_test, y_proba),
            "accuracy":      accuracy_score(y_test, y_pred_opt),
            "precision":     precision_score(y_test, y_pred_opt, zero_division=0),
            "recall":        recall_score(y_test, y_pred_opt, zero_division=0),
            "best_threshold": best_thr,
        }

        print(f"    F1 (0.5)      : {results[name]['f1_default']:.4f}")
        print(f"    F1 (optimisé) : {results[name]['f1_optimized']:.4f}")
        print(f"    AUC           : {results[name]['auc']:.4f}")
        print(f"    AP            : {results[name]['ap']:.4f}")
        print(f"    Seuil optimal : {best_thr:.4f}")

    #  Meilleur modèle 
    best_name = max(results, key=lambda k: results[k]["f1_optimized"])
    best      = results[best_name]
    best_clf  = best["clf"]

    print(f"\n  Meilleur modèle : {best_name}")
    print(f"  F1 optimisé     : {best['f1_optimized']:.4f}")
    print(f"  AUC             : {best['auc']:.4f}")

    # Rapport détaillé 
    y_pred_best = (
        best_clf.predict_proba(X_test_scaled)[:, 1] >= best["best_threshold"]
    ).astype(int)

    print("\n" + "=" * 60)
    print("RAPPORT DE CLASSIFICATION (seuil optimisé)")
    print("=" * 60)
    print(classification_report(
        y_test, y_pred_best,
        target_names=["Non Solvable", "Solvable"]
    ))

    cm = confusion_matrix(y_test, y_pred_best)
    print("Matrice de confusion :")
    print(cm)

    # Graphiques
    # ROC curves
    plt.figure(figsize=(8, 6))
    for name, r in results.items():
        fpr, tpr, _ = roc_curve(y_test, r["clf"].predict_proba(X_test_scaled)[:, 1])
        plt.plot(fpr, tpr, linewidth=2, label=f"{name} (AUC={r['auc']:.3f})")
    plt.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Aléatoire")
    plt.xlabel("Taux de faux positifs")
    plt.ylabel("Taux de vrais positifs")
    plt.title("Courbes ROC — Comparaison des modèles")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "roc_curves.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("   roc_curves.png")

    # Matrice de confusion
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=["Non Solvable", "Solvable"],
        yticklabels=["Non Solvable", "Solvable"],
    )
    plt.title(f"Matrice de confusion — {best_name}")
    plt.ylabel("Réel")
    plt.xlabel("Prédit")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "confusion_matrix.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("   confusion_matrix.png")

    # Heatmap de corrélation (numériques uniquement, corr avec y_test)
    X_test_df = pd.DataFrame(X_test_scaled, columns=feature_names)
    corr_num  = X_test_df[NUMERIC_FEATURES].copy()
    corr_num["SOLVABLE"] = y_test.values
    corr_matrix = corr_num.corr()

    target_corr  = corr_matrix["SOLVABLE"].drop("SOLVABLE").abs().sort_values(ascending=False)
    top_features = target_corr.head(12).index.tolist() + ["SOLVABLE"]
    sub_corr     = corr_matrix.loc[top_features, top_features]

    plt.figure(figsize=(12, 10))
    sns.heatmap(
        sub_corr, annot=True, fmt=".2f", cmap="RdYlGn",
        linewidths=0.4, annot_kws={"size": 8},
        vmin=-1, vmax=1, center=0,
    )
    plt.title("Top 12 features — Corrélation avec SOLVABLE")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "correlation_top15.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("   correlation_top15.png")

    # SHAP 
    print("\nGénération des explications SHAP...")
    n_sample = min(300, len(X_test_scaled))
    X_shap   = X_test_scaled[:n_sample]

    try:
        if best_name in ("RF", "XGB"):
            explainer   = shap.TreeExplainer(best_clf)
            shap_values = explainer.shap_values(X_shap)
            sv_plot = shap_values[1] if isinstance(shap_values, list) else shap_values
        else:
            explainer   = shap.LinearExplainer(best_clf, X_shap)
            shap_values = explainer.shap_values(X_shap)
            sv_plot     = shap_values

        # Summary plot
        plt.figure()
        shap.summary_plot(
            sv_plot, X_shap,
            feature_names=feature_names,
            show=False, max_display=16,
        )
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "shap_summary.png"), dpi=150, bbox_inches="tight")
        plt.close()
        print("  ✓ shap_summary.png")

        # Feature importance globale depuis SHAP
        shap_importance = pd.DataFrame({
            "feature":    feature_names,
            "importance": np.abs(sv_plot).mean(axis=0),
        }).sort_values("importance", ascending=False)

        shap_importance.to_csv(
            os.path.join(MODELS_DIR, "shap_feature_importance.csv"), index=False
        )
        print("  ✓ shap_feature_importance.csv")

    except Exception as e:
        print(f"  SHAP non disponible : {e}")
        explainer = None

    # Sauvegarde des artefacts 
    print("\nSauvegarde des artefacts...")

    joblib.dump(best_clf,      os.path.join(MODELS_DIR, "model.pkl"))
    joblib.dump(scaler,        os.path.join(MODELS_DIR, "scaler.pkl"))
    joblib.dump(feature_names, os.path.join(MODELS_DIR, "features.pkl"))
    joblib.dump(encoders,      os.path.join(MODELS_DIR, "encoders.pkl"))
    joblib.dump(best["best_threshold"], os.path.join(MODELS_DIR, "best_threshold.pkl"))
    joblib.dump(NUMERIC_FEATURES,
            os.path.join(MODELS_DIR, "numeric_features.pkl"))

    joblib.dump(CATEGORICAL_FEATURES,
            os.path.join(MODELS_DIR, "categorical_features.pkl"))

    if explainer is not None:
        with open(os.path.join(MODELS_DIR, "shap_explainer.pkl"), "wb") as f:
            pickle.dump(explainer, f)
        print("  ✓ shap_explainer.pkl")

    # Rapport de comparaison JSON 
    import json
    comparison = {
        name: {
            "f1":       round(r["f1_optimized"], 4),
            "auc":      round(r["auc"], 4),
            "ap":       round(r["ap"], 4),
            "accuracy": round(r["accuracy"], 4),
            "threshold":round(r["best_threshold"], 4),
        }
        for name, r in results.items()
    }
    with open(os.path.join(MODELS_DIR, "comparison_report.json"), "w") as f:
        json.dump(comparison, f, indent=2)

    print("   model.pkl")
    print("   scaler.pkl")
    print("   features.pkl")
    print("   encoders.pkl")
    print("   best_threshold.pkl")
    print("   comparison_report.json")

    print("\n" + "=" * 60)
    print("TRAINING TERMINÉ")
    print("=" * 60)

    return {
        "model":      best_clf,
        "scaler":     scaler,
        "explainer":  explainer,
        "features":   feature_names,
        "encoders":   encoders,
        "model_type": best_name,
        "metrics": {
            "accuracy":  round(best["accuracy"],     4),
            "precision": round(best["precision"],    4),
            "recall":    round(best["recall"],       4),
            "f1":        round(best["f1_optimized"], 4),
            "roc_auc":   round(best["auc"],          4),
        },
    }



# POINT D'ENTRÉE DIRECT

if __name__ == "__main__":
    result = run_training()

    print("\nRÉSULTAT FINAL :")
    print(f"  Modèle   : {result['model_type']}")
    print(f"  F1       : {result['metrics']['f1']}")
    print(f"  AUC      : {result['metrics']['roc_auc']}")
    print(f"  Accuracy : {result['metrics']['accuracy']}")
    print("\nProchaine étape → python 04_xai_explain.py")