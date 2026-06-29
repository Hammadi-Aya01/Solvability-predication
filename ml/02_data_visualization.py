# 02_data_visualization.py
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import os

# Chemins
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
DATA_PATH  = os.path.join(DATA_DIR, "dataset_clean.csv")

os.makedirs(CHARTS_DIR, exist_ok=True)

# Chargement
print("=" * 60)
print("CHARGEMENT DES DONNÉES")
print("=" * 60)

df = pd.read_csv(DATA_PATH)
print(f"Dataset chargé : {df.shape[0]} clients, {df.shape[1]} colonnes")
print(f"Colonnes disponibles :\n  {sorted(df.columns.tolist())}")

# Thème global
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "white",
    "font.size":        11,
})

COLORS = {
    "solvable":     "#2ecc71",
    "non_solvable": "#e74c3c",
    "primary":      "#3498db",
    "secondary":    "#9b59b6",
    "warning":      "#f39c12",
}

# Label lisible pour la cible
df["SOLVABLE_LABEL"] = df["SOLVABLE"].map({0: "Non solvable", 1: "Solvable"})

# Helpers 
def col_exists(name):
    """Retourne True si la colonne existe dans df."""
    return name in df.columns


def save(filename):
    path = os.path.join(CHARTS_DIR, filename)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ {filename} sauvegardé")


# GRAPHIQUE 1 — Distribution solvable / non-solvable
print("\n" + "=" * 60)
print("GRAPHIQUE 1 — Distribution des clients")
print("=" * 60)

counts = df["SOLVABLE"].value_counts().sort_index()
labels = ["Non solvable", "Solvable"]
colors = [COLORS["non_solvable"], COLORS["solvable"]]

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle("Répartition des clients par solvabilité", fontsize=14, fontweight="bold")

# Camembert
axes[0].pie(
    counts, labels=labels, colors=colors,
    autopct="%1.1f%%", startangle=90,
    wedgeprops={"edgecolor": "white", "linewidth": 1.5},
)
axes[0].set_title("Proportion")

# Barres
bars = axes[1].bar(labels, counts, color=colors, width=0.5, edgecolor="white")
axes[1].set_title("Effectifs")
axes[1].set_ylabel("Nombre de clients")
axes[1].set_ylim(0, counts.max() * 1.15)

for bar, count in zip(bars, counts):
    axes[1].text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + counts.max() * 0.02,
        f"{count:,}",
        ha="center", fontweight="bold", fontsize=12,
    )

save("01_distribution.png")


# GRAPHIQUE 2 — Distribution du retard pondéré
# (RETARD_MOYEN supprimé du CSV → on utilise RETARD_PONDERE)
print("\n" + "=" * 60)
print("GRAPHIQUE 2 — Analyse des retards")
print("=" * 60)

# Choix de la colonne de retard disponible
if col_exists("RETARD_PONDERE"):
    retard_col   = "RETARD_PONDERE"
    retard_label = "Retard pondéré (jours × montant)"
elif col_exists("RETARD_MOYEN"):
    retard_col   = "RETARD_MOYEN"
    retard_label = "Retard moyen (jours)"
else:
    retard_col   = None

if retard_col:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Analyse des retards de paiement", fontsize=14, fontweight="bold")

    # Distribution globale
    axes[0].hist(
        df[retard_col].clip(-60, 200), bins=40,
        color=COLORS["primary"], edgecolor="white", alpha=0.85,
    )
    axes[0].axvline(x=0, color="red",    linestyle="--", linewidth=1.5, label="Référence 0 j")
    axes[0].axvline(
        x=df[retard_col].mean(), color="orange", linestyle="--",
        linewidth=1.5, label=f"Moyenne ({df[retard_col].mean():.1f})",
    )
    axes[0].set_title(f"Distribution : {retard_label}")
    axes[0].set_xlabel("Valeur (outliers tronqués à [-60, 200])")
    axes[0].set_ylabel("Nombre de clients")
    axes[0].legend()

    # Boxplot par statut
    sol_data   = df.loc[df["SOLVABLE"] == 1, retard_col]
    nsol_data  = df.loc[df["SOLVABLE"] == 0, retard_col]
    bp = axes[1].boxplot(
        [nsol_data, sol_data],
        labels=["Non solvable", "Solvable"],
        patch_artist=True,
        medianprops={"color": "black", "linewidth": 2},
    )
    bp["boxes"][0].set_facecolor(COLORS["non_solvable"])
    bp["boxes"][0].set_alpha(0.7)
    bp["boxes"][1].set_facecolor(COLORS["solvable"])
    bp["boxes"][1].set_alpha(0.7)
    axes[1].set_title(f"{retard_label} par statut")
    axes[1].set_ylabel(retard_label)

    save("02_retard.png")
else:
    print("  ⚠ Aucune colonne de retard disponible — graphique 2 ignoré.")


# =============================================================================
# GRAPHIQUE 3 — Matrice de corrélation
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 3 — Corrélations")
print("=" * 60)

numeric_cols = df.select_dtypes(include=[np.number]).drop(columns=["SOLVABLE"], errors="ignore")
corr_full    = df.select_dtypes(include=[np.number]).corr()

plt.figure(figsize=(13, 10))
mask = np.triu(np.ones_like(corr_full, dtype=bool))   # triangle supérieur masqué
sns.heatmap(
    corr_full, mask=mask,
    annot=True, fmt=".2f", cmap="RdYlGn",
    linewidths=0.4, linecolor="white",
    annot_kws={"size": 7},
    vmin=-1, vmax=1, center=0,
)
plt.title("Matrice de corrélation (triangle inférieur)", fontsize=13, fontweight="bold")
save("03_correlation.png")


# =============================================================================
# GRAPHIQUE 4 — Corrélation des variables avec SOLVABLE
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 4 — Corrélation avec la cible SOLVABLE")
print("=" * 60)

target_corr = corr_full["SOLVABLE"].drop("SOLVABLE").sort_values()
bar_colors  = [COLORS["solvable"] if v >= 0 else COLORS["non_solvable"]
               for v in target_corr]

plt.figure(figsize=(9, 7))
bars = plt.barh(target_corr.index, target_corr.values, color=bar_colors, edgecolor="white")
plt.axvline(x=0, color="black", linewidth=0.8)
plt.title("Corrélation des variables avec SOLVABLE", fontsize=13, fontweight="bold")
plt.xlabel("Corrélation de Pearson")

# Valeurs sur les barres
for bar, val in zip(bars, target_corr.values):
    x_pos = val + 0.005 if val >= 0 else val - 0.005
    ha    = "left"      if val >= 0 else "right"
    plt.text(x_pos, bar.get_y() + bar.get_height() / 2,
             f"{val:.3f}", va="center", ha=ha, fontsize=8)

patches = [
    mpatches.Patch(color=COLORS["solvable"],     label="Corrélation positive"),
    mpatches.Patch(color=COLORS["non_solvable"], label="Corrélation négative"),
]
plt.legend(handles=patches, loc="lower right")
save("04_importance.png")


# =============================================================================
# GRAPHIQUE 5 — Répartition par région (gouvernorat)
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 5 — Répartition par région")
print("=" * 60)

region_col = "GOUVERNORAT_LABEL" if col_exists("GOUVERNORAT_LABEL") else "GOUVERNORAT"

if col_exists(region_col):
    region_data = (
        df.groupby([region_col, "SOLVABLE"])
        .size()
        .unstack(fill_value=0)
        .rename(columns={0: "Non solvable", 1: "Solvable"})
    )
    # Trier par total décroissant
    region_data = region_data.loc[region_data.sum(axis=1).sort_values(ascending=False).index]

    ax = region_data.plot(
        kind="bar", figsize=(14, 6),
        color=[COLORS["non_solvable"], COLORS["solvable"]],
        edgecolor="white",
    )
    ax.set_title("Clients par gouvernorat", fontsize=13, fontweight="bold")
    ax.set_xlabel("Gouvernorat")
    ax.set_ylabel("Nombre de clients")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.legend(title="Statut")
    save("05_region.png")
else:
    print(f"  ⚠ Colonne '{region_col}' absente — graphique 5 ignoré.")


# =============================================================================
# GRAPHIQUE 6 — Nombre de retards vs solvabilité
# (TAUX_RETARD supprimé du CSV → on utilise NB_RETARDS disponible)
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 6 — Nombre de retards par statut")
print("=" * 60)

# Choix de la colonne de retard disponible dans le CSV
if col_exists("TAUX_RETARD"):
    retard_box_col   = "TAUX_RETARD"
    retard_box_label = "Taux de retard (%)"
elif col_exists("NB_RETARDS"):
    retard_box_col   = "NB_RETARDS"
    retard_box_label = "Nombre de paiements en retard"
else:
    retard_box_col = None

if retard_box_col:
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    fig.suptitle(f"{retard_box_label} selon la solvabilité",
                 fontsize=13, fontweight="bold")

    # Boxplot
    sns.boxplot(
        x="SOLVABLE_LABEL", y=retard_box_col, data=df,
        order=["Non solvable", "Solvable"],
        palette={"Non solvable": COLORS["non_solvable"], "Solvable": COLORS["solvable"]},
        ax=axes[0],
    )
    axes[0].set_title("Boxplot")
    axes[0].set_xlabel("Statut")
    axes[0].set_ylabel(retard_box_label)

    # Violinplot
    sns.violinplot(
        x="SOLVABLE_LABEL", y=retard_box_col, data=df,
        order=["Non solvable", "Solvable"],
        palette={"Non solvable": COLORS["non_solvable"], "Solvable": COLORS["solvable"]},
        inner="quartile", ax=axes[1],
    )
    axes[1].set_title("Violinplot")
    axes[1].set_xlabel("Statut")
    axes[1].set_ylabel(retard_box_label)

    save("06_retards_statut.png")
else:
    print("  ⚠ Aucune colonne de retard disponible — graphique 6 ignoré.")


# =============================================================================
# GRAPHIQUE 7 — Montant TTC vs solvabilité
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 7 — Montant TTC vs solvabilité")
print("=" * 60)

if col_exists("TOTAL_MONTANT_TTC"):
    # Limiter les outliers extrêmes (99e percentile)
    cap = df["TOTAL_MONTANT_TTC"].quantile(0.99)
    df_plot = df[df["TOTAL_MONTANT_TTC"] <= cap].copy()

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    fig.suptitle("CA Total TTC selon la solvabilité", fontsize=13, fontweight="bold")

    sns.histplot(
        data=df_plot, x="TOTAL_MONTANT_TTC", hue="SOLVABLE_LABEL",
        hue_order=["Non solvable", "Solvable"],
        palette={"Non solvable": COLORS["non_solvable"], "Solvable": COLORS["solvable"]},
        bins=35, alpha=0.7, ax=axes[0],
    )
    axes[0].set_title("Distribution (outliers à 99% tronqués)")
    axes[0].set_xlabel("Montant TTC (DT)")

    sns.boxplot(
        x="SOLVABLE_LABEL", y="TOTAL_MONTANT_TTC", data=df_plot,
        order=["Non solvable", "Solvable"],
        palette={"Non solvable": COLORS["non_solvable"], "Solvable": COLORS["solvable"]},
        ax=axes[1],
    )
    axes[1].set_title("Boxplot")
    axes[1].set_xlabel("Statut")
    axes[1].set_ylabel("Montant TTC (DT)")

    save("07_montant_ttc.png")


# =============================================================================
# GRAPHIQUE 8 — Ratio paiement vs solvabilité
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 8 — Ratio de paiement")
print("=" * 60)

if col_exists("RATIO_PAIEMENT"):
    # Clamp entre 0 et 2 (valeurs aberrantes possibles)
    df_rp = df[df["RATIO_PAIEMENT"].between(0, 2)].copy()

    plt.figure(figsize=(9, 6))
    for label, grp in df_rp.groupby("SOLVABLE_LABEL"):
        color = COLORS["solvable"] if label == "Solvable" else COLORS["non_solvable"]
        plt.hist(grp["RATIO_PAIEMENT"], bins=35, alpha=0.6,
                 color=color, label=label, edgecolor="white")

    plt.axvline(x=1.0, color="black", linestyle="--", linewidth=1.2,
                label="Ratio parfait = 1.0")
    plt.title("Ratio de paiement (réglé / facturé)", fontsize=13, fontweight="bold")
    plt.xlabel("Ratio paiement")
    plt.ylabel("Nombre de clients")
    plt.legend()
    save("08_ratio_paiement.png")


# =============================================================================
# GRAPHIQUE 9 — Ancienneté client vs solvabilité
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 9 — Ancienneté client")
print("=" * 60)

if col_exists("ANCIENNETE_CLIENT"):
    plt.figure(figsize=(9, 6))
    for label, grp in df.groupby("SOLVABLE_LABEL"):
        color = COLORS["solvable"] if label == "Solvable" else COLORS["non_solvable"]
        plt.hist(grp["ANCIENNETE_CLIENT"], bins=35, alpha=0.6,
                 color=color, label=label, edgecolor="white")

    plt.title("Ancienneté des clients (jours)", fontsize=13, fontweight="bold")
    plt.xlabel("Ancienneté (jours)")
    plt.ylabel("Nombre de clients")
    plt.legend()
    save("09_anciennete.png")


# =============================================================================
# GRAPHIQUE 10 — Répartition par nature client
# =============================================================================
print("\n" + "=" * 60)
print("GRAPHIQUE 10 — Nature client")
print("=" * 60)

nature_col = "NATURE_CLIENT_LABEL" if col_exists("NATURE_CLIENT_LABEL") else "NATURE_CLIENT"

if col_exists(nature_col):
    # ── Agrégation ────────────────────────────────────────────────────────────
    nd = (
        df.groupby([nature_col, "SOLVABLE"])
        .size()
        .unstack(fill_value=0)
    )
    col_map = {}
    if 0 in nd.columns: col_map[0] = "Non solvable"
    if 1 in nd.columns: col_map[1] = "Solvable"
    nd = nd.rename(columns=col_map)
    if "Non solvable" not in nd.columns: nd["Non solvable"] = 0
    if "Solvable"     not in nd.columns: nd["Solvable"]     = 0

    nd["Total"] = nd["Solvable"] + nd["Non solvable"]
    nd["Taux"]  = (nd["Solvable"] / nd["Total"] * 100).round(1)

    # ── Regrouper catégories rares (≤ 5 clients) sous "Autres" ───────────────
    MIN_CLIENTS = 5
    small = nd[nd["Total"] <= MIN_CLIENTS]
    nd    = nd[nd["Total"] >  MIN_CLIENTS].copy()
    if len(small) > 0:
        tot_s = small["Total"].sum()
        nd.loc[f"Autres ({len(small)} cat.)"] = {
            "Solvable":     small["Solvable"].sum(),
            "Non solvable": small["Non solvable"].sum(),
            "Total":        tot_s,
            "Taux":         round(small["Solvable"].sum() / tot_s * 100, 1) if tot_s > 0 else 0,
        }

    # Trier par total croissant (barh : plus grand en haut)
    nd = nd.sort_values("Total", ascending=True)
    n  = len(nd)

    fig, axes = plt.subplots(1, 2, figsize=(16, max(7, n * 0.45 + 2)))
    fig.patch.set_facecolor("white")
    fig.suptitle("Solvabilité par nature de client", fontsize=14, fontweight="bold", y=1.01)

    y_pos = np.arange(n)

    # ── Gauche : barres horizontales empilées ─────────────────────────────────
    ax0 = axes[0]
    ax0.set_facecolor("#f8f9fa")
    ax0.set_axisbelow(True)
    ax0.grid(axis="x", color="white", linewidth=1.2)

    ax0.barh(y_pos, nd["Solvable"],
             color=COLORS["solvable"], edgecolor="white", linewidth=0.6,
             label="Solvable", height=0.6)
    ax0.barh(y_pos, nd["Non solvable"], left=nd["Solvable"].values,
             color=COLORS["non_solvable"], edgecolor="white", linewidth=0.6,
             label="Non solvable", height=0.6)

    for i, (_, row) in enumerate(nd.iterrows()):
        ax0.text(row["Total"] + nd["Total"].max() * 0.01, i,
                 f"{int(row['Total'])}", va="center", ha="left",
                 fontsize=9, color="#333333")

    ax0.set_yticks(y_pos)
    ax0.set_yticklabels(nd.index, fontsize=10)
    ax0.set_xlabel("Nombre de clients", fontsize=11)
    ax0.set_title("Effectifs par nature de client", fontsize=12, fontweight="bold", pad=10)
    ax0.set_xlim(0, nd["Total"].max() * 1.18)
    ax0.legend(loc="lower right", framealpha=0.9, fontsize=10)
    ax0.spines[["top", "right"]].set_visible(False)

    # ── Droite : taux de solvabilité horizontal, coloré par seuil ────────────
    ax1 = axes[1]
    ax1.set_facecolor("#f8f9fa")
    ax1.set_axisbelow(True)
    ax1.grid(axis="x", color="white", linewidth=1.2)

    taux_colors = [
        COLORS["solvable"]     if t >= 90
        else COLORS["primary"] if t >= 70
        else COLORS["non_solvable"]
        for t in nd["Taux"]
    ]
    ax1.barh(y_pos, nd["Taux"], color=taux_colors,
             edgecolor="white", linewidth=0.6, height=0.6)
    ax1.axvline(x=90, color="#888888", linestyle="--", linewidth=1.2,
                label="Seuil 90%", zorder=3)

    for i, (_, row) in enumerate(nd.iterrows()):
        t = row["Taux"]
        if t >= 15:
            ax1.text(t - 1.5, i, f"{t:.1f}%", va="center", ha="right",
                     fontsize=9, color="white", fontweight="bold")
        else:
            ax1.text(t + 1.0, i, f"{t:.1f}%", va="center", ha="left",
                     fontsize=9, color="#333333", fontweight="bold")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(nd.index, fontsize=10)
    ax1.set_xlabel("Taux de solvabilité (%)", fontsize=11)
    ax1.set_title("Taux de solvabilité par nature", fontsize=12, fontweight="bold", pad=10)
    ax1.set_xlim(0, 115)

    legend_patches = [
        mpatches.Patch(color=COLORS["solvable"],     label="≥ 90%  (très bon)"),
        mpatches.Patch(color=COLORS["primary"],      label="70–89% (moyen)"),
        mpatches.Patch(color=COLORS["non_solvable"], label="< 70%  (risqué)"),
    ]
    ax1.legend(handles=legend_patches, loc="lower right", framealpha=0.9, fontsize=9)
    ax1.spines[["top", "right"]].set_visible(False)

    save("10_nature_client.png")


# =============================================================================
# RÉSUMÉ FINAL
# =============================================================================
print("\n" + "=" * 60)
print("ANALYSE TERMINÉE AVEC SUCCÈS")
print("=" * 60)
print(f"Dataset           : {len(df)} clients")
print(f"Solvables         : {df['SOLVABLE'].sum()}")
print(f"Non solvables     : {(df['SOLVABLE'] == 0).sum()}")
print(f"Taux solvabilité  : {df['SOLVABLE'].mean()*100:.1f}%")

if col_exists("RETARD_PONDERE"):
    print(f"Retard pondéré moy: {df['RETARD_PONDERE'].mean():.2f}")
if col_exists("NB_RETARDS"):
    print(f"Nb retards moyen  : {df['NB_RETARDS'].mean():.1f}")

print(f"\nCharts sauvegardés dans : {CHARTS_DIR}")
print("\nProchaine étape → python 03_ml_models.py")