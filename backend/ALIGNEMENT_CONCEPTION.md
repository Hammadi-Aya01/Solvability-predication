# Alignement backend avec conception UML

Ce backend a été corrigé pour respecter les actions décrites dans `conception.pdf` sans modifier la conception.

## Cas d'utilisation couverts

- S'authentifier: `POST /api/auth/login`
- Gérer les utilisateurs: `GET/POST/PUT/DELETE /api/auth/users`
- Consulter l'historique système: `GET /api/dashboard/historique-systeme`
- Importer un dataset: `POST /api/datasets/upload`
- Entraîner le modèle: `POST /api/datasets/<id>/train`
- Visualiser les résultats d'entraînement: `GET /api/models`, `GET /api/models/<id>`
- Consulter les résultats de solvabilité: `GET /api/predict/solvabilite`
- Rechercher un client: `GET /api/clients?q=...`
- Consulter profil client: `GET /api/clients/<id>/profile`
- Consulter score risque: `GET /api/clients/<id>/score`
- Consulter explications SHAP: `GET /api/clients/<id>/explications-shap`
- Analyser historique paiement: `GET /api/clients/<id>/historique-paiement`
- Analyser comportement commercial: `GET /api/clients/<id>/comportement-commercial`

## Corrections principales

- Correction du sens de prédiction: `1 = SOLVABLE`, `0 = NON-SOLVABLE`, comme dans le pipeline ML.
- Le score de risque est calculé à partir de la probabilité de non-solvabilité.
- Le training suit l'ordre des diagrammes: charger dataset, préparer données, entraîner, évaluer, générer scores, générer SHAP, sauvegarder modèle, afficher résultats.
- Les explications SHAP sont persistées dans `ExplicationSHAP` après les prédictions.
- Les algorithmes sont alignés avec le code ML fourni: Régression Logistique, Random Forest, XGBoost.
- Ajout d'une couche de compatibilité avec les noms UML: `Utilisateur`, `Admin`, `ResponsableFinancier`, `ModeleML`, `HistoriquePaiement`, `HistoriqueSysteme`.
- Réparation automatique de schéma SQLite local pour éviter les erreurs du type `no such column`.
- Suppression de `venv`, `__pycache__` et ancienne base SQLite du zip.

## Démarrage conseillé

```powershell
cd E:\credit-scoring\backend
C:\Users\Aya\AppData\Local\Programs\Python\Python311\python.exe -m venv venv
.\venv\Scripts\activate
python --version
pip install -r requirements.txt
python app.py
```
