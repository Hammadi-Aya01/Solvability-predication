# Changements roles - agent financier

Cette version garde le role ADMIN comme avant et limite le role agent/responsable financier a la consultation, conformement a la conception.

## Agent / responsable financier autorise
- Consulter le dashboard et les analyses issues du dataset entraine.
- Consulter la liste des clients et rechercher par code client / nom.
- Consulter le profil client.
- Consulter score de risque, explications SHAP, historique de paiement et comportement commercial.
- Consulter les resultats de solvabilite et les resultats/modeles deja entraines.

## Agent / responsable financier interdit
- Upload dataset.
- Lancer training / synchronisation dataset.
- Creer, modifier, supprimer clients.
- Changer plafond credit, relances, alertes.
- Prediction manuelle/bulk qui modifie les donnees.
- Voir historique systeme / audit log: connexions, deconnexions, actions admin.
- Gestion utilisateurs.

## Admin
Le role ADMIN reste complet: dataset, training, modeles, utilisateurs, historique systeme, actions de modification.
