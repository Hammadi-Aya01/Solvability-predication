# Changements backend

- Correction de la recherche clients: les clients avec score_actuel NULL ne sont plus exclus automatiquement.
- Ajout de la commande CLI `flask seed-admin` pour créer ou réinitialiser un administrateur local.

Commande admin:

```powershell
$env:FLASK_APP="app:create_app"
flask seed-admin --email "hammadiaya2004@gmail.com" --password "Admin123!"
```
