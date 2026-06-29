# Changements appliqués

Demandes appliquées sans modifier la conception UML :

1. Dashboard
   - Les "Top clients à risque" ne sont plus envoyés dans l'endpoint `/api/dashboard/overview`.
   - L'affichage des top clients est déplacé vers la page Clients côté frontend.

2. Clients
   - Ajout de l'endpoint `/api/clients/top-risk`.
   - La liste Clients affiche désormais l'identité du client, sa solvabilité et son score de risque.
   - Les champs `score_risque` et `solvabilite` sont ajoutés dans `Client.to_dict()`.

3. Profil client
   - Consultation du profil client journalisée dans l'historique système.
   - Ajout d'un bloc `commercial_behavior` : total achats, total paiements, ratio paiement, retards, recommandation.

4. Historique système
   - L'historique sert maintenant aux actions des utilisateurs : login, logout, ajout/modification/suppression utilisateur, import dataset, entraînement modèle, consultation profil client, etc.
   - Les entrées retournent l'acteur, le rôle et une description lisible.
