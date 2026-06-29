#Preaparation data.py
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
#Chemins 
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR        = os.path.join(BASE_DIR, "data")
FACTURES_PATH   = os.path.join(DATA_DIR, "Data pfe solvabilité clients.xlsx") #fichier factures 
REGLEMENTS_PATH = os.path.join(DATA_DIR, "reglement client.xlsx") #fichier reglement 
OUTPUT_PATH     = os.path.join(DATA_DIR, "dataset_clean.csv")

os.makedirs(DATA_DIR, exist_ok=True)

# Chargement 
print("=" * 60)
print("CHARGEMENT DES DONNÉES")
print("=" * 60)

df_factures   = pd.read_excel(FACTURES_PATH)
df_reglements = pd.read_excel(REGLEMENTS_PATH)

# Normalisation des noms de colonnes (strip des espaces + upper)
df_factures.columns   = df_factures.columns.str.strip().str.upper()
df_reglements.columns = df_reglements.columns.str.strip().str.upper()

print(f"Factures   : {len(df_factures)} lignes   | Colonnes : {list(df_factures.columns)}")
print(f"Règlements : {len(df_reglements)} lignes  | Colonnes : {list(df_reglements.columns)}")

# Conversion des dates
df_factures["DATE_FACTURE"]       = pd.to_datetime(df_factures["DATE_FACTURE"],       errors="coerce")
df_reglements["DATE"]             = pd.to_datetime(df_reglements["DATE"],             errors="coerce")
df_reglements["DATE_ECHEANCE"]    = pd.to_datetime(df_reglements["DATE ECHEANCE"],    errors="coerce")
                    ### new features ###
# Calcul du retard (en jours)
# Positif = payé en retard, négatif = payé en avance
df_reglements["RETARD_JOURS"] = (
    df_reglements["DATE"] - df_reglements["DATE_ECHEANCE"]
).dt.days

# Date de référence pour l'inactivité (dernière facture connue)
ref_date = df_factures["DATE_FACTURE"].max()

print(f"\nDate de référence : {ref_date.date()}")

# FONCTIONS D'AGRÉGATION (sur Series simples → compatibles .agg())
#Moyenne achat 
def freq_purchase(dates):
    """Fréquence moyenne entre achats (jours)"""
    d = pd.to_datetime(dates, errors="coerce").dropna().unique()
    if len(d) < 2:
        return 0.0
    diffs = np.diff(np.sort(d))
    days  = diffs.astype("timedelta64[D]").astype(float)
    return float(days.mean())

#Anciennete client 
def anciennete_client(dates):
    """Durée entre première et dernière facture (jours)"""
    d = pd.to_datetime(dates, errors="coerce").dropna()
    if len(d) == 0:
        return 0.0
    return float((d.max() - d.min()).days)

#To see if a client actif or not 
def jours_depuis_dernier_achat(dates):
    """Nombre de jours depuis la dernière facture."""
    d = pd.to_datetime(dates, errors="coerce").dropna()
    if len(d) == 0:
        return 9999.0   # client inactif
    return float((ref_date - d.max()).days)


# FEATURES FACTURES
print("\n" + "=" * 60)
print("CONSTRUCTION DES FEATURES FACTURES")
print("=" * 60)

invoice_features = (
    df_factures
    .groupby("CODE CLIENT")
    .agg(
        TOTAL_MONTANT_TTC          = ("MONTANT_TTC",    "sum"),
        NB_FACTURES                = ("MONTANT_TTC",    "count"),
        MONTANT_MOY_FACTURE        = ("MONTANT_TTC",    "mean"),
        MONTANT_MAX_FACTURE        = ("MONTANT_TTC",    "max"),
        NATURE_CLIENT              = ("NATURE CLIENT",  "first"),
        GOUVERNORAT                = ("GOUVERNORAT",    "first"),
        FREQUENCE_ACHAT            = ("DATE_FACTURE",   freq_purchase),
        ANCIENNETE_CLIENT          = ("DATE_FACTURE",   anciennete_client),
        JOURS_DEPUIS_DERNIER_ACHAT = ("DATE_FACTURE",   jours_depuis_dernier_achat),
    )
    .reset_index()
)

print(f"  ✓ {len(invoice_features)} clients avec factures")

# FEATURES RÈGLEMENTS  
print("\n" + "=" * 60)
print("CONSTRUCTION DES FEATURES RÈGLEMENTS")
print("=" * 60)

payment_features = (
    df_reglements
    .groupby("CODE CLIENT")
    .agg(
        TOTAL_MONTANT_REG  = ("MONTANT REG",   "sum"),
        NB_REGLEMENTS      = ("MONTANT REG",   "count"),
        MONTANT_MOY_REG    = ("MONTANT REG",   "mean"),
        RETARD_MOYEN       = ("RETARD_JOURS",  "mean"),
        RETARD_MAX         = ("RETARD_JOURS",  "max"),
        NB_RETARDS         = ("RETARD_JOURS",  lambda x: (x > 0).sum()),
        NB_MODES_PAIEMENT  = ("MODE",          "nunique"),
        RETARD_STD         = ("RETARD_JOURS",  lambda x: x.std(ddof=0) if len(x) > 1 else 0.0),
    )
    .reset_index()
)

# RETARD_PONDERE calculé séparément 

df_reglements["_WEIGHTED_RETARD"] = (
    df_reglements["RETARD_JOURS"] * df_reglements["MONTANT REG"]
)

retard_pondere_df = (
    df_reglements
    .groupby("CODE CLIENT")
    .apply(
        lambda g: (
            g["_WEIGHTED_RETARD"].sum() / g["MONTANT REG"].sum()
            if g["MONTANT REG"].sum() != 0
            else 0.0
        ),
        include_groups=False,    # pandas >= 2.2 : exclut la clé de groupby
    )
    .reset_index()
    .rename(columns={0: "RETARD_PONDERE"})
)

# Nettoyage de la colonne temporaire
df_reglements.drop(columns=["_WEIGHTED_RETARD"], inplace=True)

# Fusion du retard pondéré dans payment_features
payment_features = payment_features.merge(retard_pondere_df, on="CODE CLIENT", how="left")
payment_features["RETARD_PONDERE"] = payment_features["RETARD_PONDERE"].fillna(0.0)

# Taux de retard (%) = NB_RETARDS / NB_REGLEMENTS × 100
payment_features["TAUX_RETARD"] = np.where(
    payment_features["NB_REGLEMENTS"] > 0,
    (payment_features["NB_RETARDS"] / payment_features["NB_REGLEMENTS"] * 100).round(2),
    0.0,
)

print(f"  ✓ {len(payment_features)} clients avec règlements")

# FUSION OUTER 
print("\n" + "=" * 60)
print("FUSION OUTER (aucun client perdu)")
print("=" * 60)

df_merged = pd.merge(invoice_features, payment_features, on="CODE CLIENT", how="outer")

# Valeurs manquantes
numeric_cols = df_merged.select_dtypes(include=[np.number]).columns
df_merged[numeric_cols] = df_merged[numeric_cols].fillna(0)

for col in ["NATURE_CLIENT", "GOUVERNORAT"]:
    if col in df_merged.columns:
        df_merged[col] = df_merged[col].fillna("INCONNU")

print(f"  ✓ {len(df_merged)} clients après fusion")

# FEATURES DÉRIVÉES

print("\n" + "=" * 60)
print("CALCUL DES FEATURES DÉRIVÉES")
print("=" * 60)

# Ratio montant réglé / montant facturé  (0–∞, peut dépasser 1 en cas d'avances)
df_merged["RATIO_PAIEMENT"] = np.where(
    df_merged["TOTAL_MONTANT_TTC"] > 0,
    (df_merged["TOTAL_MONTANT_REG"] / df_merged["TOTAL_MONTANT_TTC"]).round(4),
    0.0,
)

# Part du CA du client sur le CA total
total_ca = df_merged["TOTAL_MONTANT_TTC"].sum()
df_merged["PART_CA_CLIENT"] = np.where(
    total_ca > 0,
    (df_merged["TOTAL_MONTANT_TTC"] / total_ca).round(6),
    0.0,
)

print("  ✓ RATIO_PAIEMENT calculé")
print("  ✓ PART_CA_CLIENT calculé")

# VARIABLE CIBLE
print("\n" + "=" * 60)
print("CALCUL DE LA VARIABLE CIBLE (SOLVABLE)")
print("=" * 60)

df_merged["SOLVABLE"] = (
    (df_merged["RETARD_MOYEN"] <= 0) &
    (df_merged["RETARD_MAX"]   <= 30) &
    (df_merged["TAUX_RETARD"]  <  20)
).astype(int)

print(f"  ✓ Solvables     : {df_merged['SOLVABLE'].sum()}")
print(f"  ✓ Non-solvables : {(df_merged['SOLVABLE'] == 0).sum()}")
print(f"  ✓ Taux solvabilité : {df_merged['SOLVABLE'].mean()*100:.1f}%")

# SUPPRESSION DES FEATURES DE DATA LEAKAGE
leak_features = ["RETARD_MOYEN", "RETARD_MAX", "TAUX_RETARD"]
df_merged.drop(columns=leak_features, errors="ignore", inplace=True)
print(f"\n  ✓ Features de leakage supprimées : {leak_features}")

# LABELS POUR LES GRAPHIQUES (conservés tels quels pour le dashboard)
df_merged["NATURE_CLIENT_LABEL"] = df_merged["NATURE_CLIENT"]
df_merged["GOUVERNORAT_LABEL"]   = df_merged["GOUVERNORAT"]

# SAUVEGARDE
df_merged.to_csv(OUTPUT_PATH, index=False)

print("\n" + "=" * 60)
print("PRÉPARATION TERMINÉE AVEC SUCCÈS")
print("=" * 60)
print(f"Dataset sauvegardé : {OUTPUT_PATH}")
print(f"Shape final        : {df_merged.shape}")
print(f"Clients totaux     : {len(df_merged)}")
print(f"Solvables          : {df_merged['SOLVABLE'].sum()}")
print(f"Non-solvables      : {(df_merged['SOLVABLE'] == 0).sum()}")

print("\nColonnes finales :")
for col in sorted(df_merged.columns):
    dtype = df_merged[col].dtype
    print(f"  ✓ {col:<35} ({dtype})")

print("\nProchaine étape → python 02_data_visualization.py")