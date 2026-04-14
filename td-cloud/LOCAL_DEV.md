# Developpement local (Phase 2)

En local, GCP Pub/Sub n'est pas disponible. Deux options :

## Option A - Emulateur Pub/Sub (recommande)

1. Lancer l'emulateur dans un terminal separe :

```powershell
gcloud beta emulators pubsub start --project=test-project
```

2. Dans le terminal du serveur, definir les variables d'environnement :

```powershell
$env:PUBSUB_EMULATOR_HOST = "localhost:8085"
$env:GCP_PROJECT_ID = "test-project"
$env:TOPIC_NAME = "redis-updates"
```

3. Creer le topic et les subscriptions (les commandes ciblent l'emulateur automatiquement) :

```powershell
gcloud pubsub topics create redis-updates --project=test-project
```

4. Lancer le serveur normalement (Gunicorn ou `python main.py`).

## Option B - Sans Pub/Sub

Pour tester uniquement le WebSocket et Redis en local, desactive Pub/Sub :

```powershell
$env:DISABLE_PUBSUB = "1"
```

Dans ce mode :
- Le serveur ne demarre pas de listener Pub/Sub.
- `POST /publish` ecrit dans Redis et emet directement un `update` en WebSocket.

## Rappel : variables utiles
- `GCP_PROJECT_ID` (par defaut `test-project`)
- `TOPIC_NAME` (par defaut `redis-updates`)
- `SUBSCRIPTION_NAME` (optionnel)
- `DISABLE_PUBSUB=1` pour l'Option B

Compatibilite maintenue avec : `PROJECT_ID`, `PUBSUB_TOPIC`, `PUBSUB_SUBSCRIPTION`.
