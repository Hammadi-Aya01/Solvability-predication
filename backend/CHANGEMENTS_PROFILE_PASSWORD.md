# Correction profil utilisateur et mot de passe

- Ajout de la route `PUT /api/auth/me/password`.
- Le changement de mot de passe exige le mot de passe actuel.
- Validation du nouveau mot de passe: 8 caractères minimum, une majuscule, un chiffre.
- Le profil utilisateur reste modifiable via `PUT /api/auth/me` pour `nom` et `prenom`.
- Action audit enregistrée: `UPDATE_PROFILE` et `CHANGE_PASSWORD`.
