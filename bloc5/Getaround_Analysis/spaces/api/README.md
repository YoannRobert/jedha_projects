---
title: Getaround Pricing API
emoji: 🚗
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# Getaround Pricing API

API de prédiction du prix journalier de location d'une voiture sur Getaround.

Le modèle est un **XGBoostRegressor** entraîné sur ~4800 voitures, servi
depuis le MLflow Model Registry via l'alias `production`.

## Endpoints

- `GET /` : message d'accueil
- `POST /predict` : prédiction du prix journalier
- `GET /docs` : documentation interactive Swagger UI

## Performance du modèle

| Métrique | Valeur  |
|----------|---------|
| MAE      | 10,30 € |
| RMSE     | 15,13 € |
| R²       | 0,790   |

## Exemple d'appel

```bash
curl -X POST https://yoannrobert-fastapi-getaround-price-prediction.hf.space/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "mileage": 100000,
        "engine_power": 110,
        "model_key": "Citroën",
        "fuel": "diesel",
        "paint_color": "black",
        "car_type": "estate",
        "private_parking_available": true,
        "has_gps": true,
        "has_air_conditioning": false,
        "automatic_car": false,
        "has_getaround_connect": true,
        "has_speed_regulator": true,
        "winter_tires": false
      }
    ]
  }'
```

Réponse :

```json
{"prediction": [105.01]}
```

## Variables d'environnement requises

- `MLFLOW_TRACKING_URI`
- `MLFLOW_TRACKING_USERNAME`
- `MLFLOW_TRACKING_PASSWORD`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Test en local

```bash
docker build -t getaround-api .
docker run --rm -p 7860:7860 --env-file .env getaround-api
```

Puis ouvrir [http://localhost:7860/docs](http://localhost:7860/docs).
