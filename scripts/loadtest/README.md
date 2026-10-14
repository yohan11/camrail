# Tests de Charge et Résilience CAMRAIL RailMind Lite

Ce dossier contient les scripts de test de charge (Locust) permettant de valider le comportement du système sous une charge simulant environ **1000 utilisateurs actifs** avec un débit nominal de **5 à 15 générations simultanées**.

---

## 1. Prérequis

Installez Locust dans votre environnement Python :
```bash
pip install locust
```

---

## 2. Commandes d'Exécution par Palier

### Palier 1 : 10 Utilisateurs Virtuels (Charge Légère / Validation)
Simule l'activité courante d'une équipe technique :
```bash
locust -f scripts/loadtest/locustfile.py --headless -u 10 -r 2 --run-time 60s --host http://localhost:8000
```

### Palier 2 : 30 Utilisateurs Virtuels (Charge Nominale / 1000 Utilisateurs Quotidiens)
Charge représentative de ~1000 utilisateurs répartis sur la journée (5 à 15 requêtes simultanées) :
```bash
locust -f scripts/loadtest/locustfile.py --headless -u 30 -r 5 --run-time 120s --host http://localhost:8000
```

### Palier 3 : 100 Utilisateurs Virtuels (Pic d'Activité / Stress Test)
Éprouve les mécanismes de régulation (File d'attente de génération et limitation de débit) :
```bash
locust -f scripts/loadtest/locustfile.py --headless -u 100 -r 10 --run-time 180s --host http://localhost:8000
```

---

## 3. Interface Web Interactive (Optionnel)

Pour observer les graphiques en temps réel :
```bash
locust -f scripts/loadtest/locustfile.py --host http://localhost:8000
```
Ouvrez ensuite votre navigateur sur : [http://localhost:8089](http://localhost:8089).

---

## 4. Indicateurs Clés à Relever

| Indicateur | Définition & Objectif | Comportement Attendu |
| :--- | :--- | :--- |
| **p50 Latence** | Médiane du temps de réponse total. | < 5s sur questions en cache ou ciblées. |
| **p95 Latence** | 95% des requêtes répondent sous ce seuil. | Mesure la file d'attente sous forte charge. |
| **TTFT (Time To First Token)** | Délai entre l'envoi de la requête et le 1er token affiché. | **< 1.5s**, donne une sensation d'instantanéité. |
| **Taux d'erreur (%)** | Pourcentage de requêtes en échec inattendu (500). | **0%**. |
| **Compteur HTTP 429** | Requêtes bridées par le Rate Limiter (fenêtre 1 min). | Normal en cas de spam (>10 req/min/user). |
| **Compteur HTTP 503** | Requêtes ayant expiré dans la file d'attente (>60s). | Normal lors des pics extrêmes (>4 LLM actifs). |
