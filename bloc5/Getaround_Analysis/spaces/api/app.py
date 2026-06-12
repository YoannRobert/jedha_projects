"""Getaround pricing API.

Expose un endpoint POST /predict qui retourne le prix journalier prédit
pour une ou plusieurs voitures, en s'appuyant sur un modèle XGBoost
chargé depuis le MLflow Model Registry au démarrage.
"""

import mlflow
import mlflow.sklearn
import os
import pandas as pd

from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal


# Constantes
REGISTERED_MODEL_NAME = "getaround-pricing"
MODEL_URI = f"models:/{REGISTERED_MODEL_NAME}@production"

# État global, peuplé au démarrage via le lifespan
state = {"model": None, "known_brands": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle depuis le registre MLflow au démarrage."""
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    model = mlflow.sklearn.load_model(MODEL_URI)

    # Extraction des marques connues du OneHotEncoder pour le remapping
    # "strict-conservateur" : toute marque non vue à l'entraînement sera
    # convertie en "Other" avant prédiction.
    preprocessor = model.named_steps["preprocessor"]
    cat_transformer = preprocessor.named_transformers_["cat"]
    cat_cols = ["model_key", "fuel", "paint_color", "car_type"]
    known_brands = set(cat_transformer.categories_[cat_cols.index("model_key")])

    state["model"] = model
    state["known_brands"] = known_brands
    yield
    # Pas de cleanup nécessaire


# Types catégoriels acceptés en entrée (toutes les modalités du dataset)
ModelKey = Literal[
    "Alfa Romeo", "Audi", "BMW", "Citroën", "Ferrari", "Fiat", "Ford",
    "Honda", "KIA Motors", "Lamborghini", "Lexus", "Maserati", "Mazda",
    "Mercedes", "Mini", "Mitsubishi", "Nissan", "Opel", "PGO", "Peugeot",
    "Porsche", "Renault", "SEAT", "Subaru", "Suzuki", "Toyota",
    "Volkswagen", "Yamaha",
]
Fuel = Literal["diesel", "electro", "hybrid_petrol", "petrol"]
PaintColor = Literal[
    "beige", "black", "blue", "brown", "green",
    "grey", "orange", "red", "silver", "white",
]
CarType = Literal[
    "convertible", "coupe", "estate", "hatchback",
    "sedan", "subcompact", "suv", "van",
]


class CarFeatures(BaseModel):
    """Caractéristiques d'une voiture pour la prédiction de prix."""

    # Désactive la protection des attributs "model_*" (Pydantic v2)
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    mileage: int = Field(..., ge=0, description="Kilométrage en km (>= 0)")
    engine_power: int = Field(..., gt=0, description="Puissance moteur (> 0)")
    model_key: ModelKey = Field(..., description="Marque du véhicule")
    fuel: Fuel = Field(..., description="Type de carburant")
    paint_color: PaintColor = Field(..., description="Couleur de la carrosserie")
    car_type: CarType = Field(..., description="Type de carrosserie")
    private_parking_available: bool
    has_gps: bool
    has_air_conditioning: bool
    automatic_car: bool
    has_getaround_connect: bool
    has_speed_regulator: bool
    winter_tires: bool


class InputPayload(BaseModel):
    """Payload accepté par l'endpoint /predict."""

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "input": [
                    {
                        "mileage": 100000,
                        "engine_power": 110,
                        "model_key": "Citroën",
                        "fuel": "diesel",
                        "paint_color": "black",
                        "car_type": "estate",
                        "private_parking_available": True,
                        "has_gps": True,
                        "has_air_conditioning": False,
                        "automatic_car": False,
                        "has_getaround_connect": True,
                        "has_speed_regulator": True,
                        "winter_tires": False,
                    },
                    {
                        "mileage": 50000,
                        "engine_power": 150,
                        "model_key": "BMW",
                        "fuel": "petrol",
                        "paint_color": "white",
                        "car_type": "coupe",
                        "private_parking_available": False,
                        "has_gps": True,
                        "has_air_conditioning": True,
                        "automatic_car": True,
                        "has_getaround_connect": True,
                        "has_speed_regulator": True,
                        "winter_tires": False,
                    },
                ]
            }
        },
    )

    input: List[CarFeatures] = Field(..., min_length=1)


class PredictionResponse(BaseModel):
    """Réponse retournée par l'endpoint /predict."""

    prediction: List[float] = Field(..., description="Liste des prix prédits en €")


# Application FastAPI
description = """
API de prédiction du prix journalier de location d'une voiture sur Getaround.

Le modèle sous-jacent est un **XGBoostRegressor** entraîné sur ~4800 voitures,
servi depuis le MLflow Model Registry via l'alias `production`.

## Performance du modèle

- MAE sur le test set : **10,30 €** (~8,7% d'erreur relative)
- RMSE : 15,13 €
- R² : 0,790

## Utilisation

L'endpoint `/predict` accepte un payload JSON avec une liste d'objets
décrivant chacun une voiture. La réponse est une liste de prix prédits
en euros, dans le même ordre que les entrées.
"""

app = FastAPI(
    title="Getaround Pricing API",
    description=description,
    version="1.0.0",
    lifespan=lifespan,
)


@app.get(path="/", tags=["Info"])
def root():
    """Page d'accueil avec un message de bienvenue et un lien vers la doc."""
    return {
        "message": "Getaround Pricing API",
        "docs": "/docs",
        "predict_endpoint": "/predict (POST)",
    }


@app.post(path="/predict", response_model=PredictionResponse, tags=["Prédiction"])
def predict(payload: InputPayload) -> PredictionResponse:
    """Prédit le prix journalier de location pour une ou plusieurs voitures.

    Accepte une liste d'objets `CarFeatures` et retourne une liste de prix
    prédits en euros, dans le même ordre que les entrées.
    """
    # Conversion en DataFrame
    df = pd.DataFrame([item.model_dump() for item in payload.input])

    # Remapping strict et conservateur : marques rares converties en "Other"
    df["model_key"] = df["model_key"].where(
        df["model_key"].isin(state["known_brands"]), "Other"
    )

    # Prédiction
    predictions = state["model"].predict(df)
    return PredictionResponse(prediction=predictions.tolist())
