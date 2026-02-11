import os
import io
import boto3
import joblib
import psycopg2
import psycopg2.extras
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
# =========================
# CONFIGURACIÓN BD
# =========================
DB_HOST = os.environ.get(
    "DB_HOST",
    "datosaemet.c16uosue6hjy.eu-north-1.rds.amazonaws.com"
)
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "datosaemet")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "MA3696dd")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# =========================
# FUNCIONES DE MODELO (S3)
# =========================
BUCKET_MODELOS = "modelos-forecasting"
MODEL_TMAX_KEY = "model_tmax.pkl"
MODEL_TMIN_KEY = "model_tmin.pkl"


def load_model(key: str):
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=BUCKET_MODELOS, Key=key)
    return joblib.load(io.BytesIO(obj["Body"].read()))


# =========================
# Pydantic
# =========================
class TemperatureResponse(BaseModel):
    numero_de_estacion: str
    ubicacion_de_la_estacion: str
    fecha: str
    temperatura_maxima: Optional[float]
    temperatura_minima: Optional[float]


class ForecastRequest(BaseModel):
    ubicacion: str
    dias: int


class PredictionResponse(BaseModel):
    dia: int
    temperatura_maxima_predicha: Optional[float]
    temperatura_minima_predicha: Optional[float]


# =========================
# FASTAPI
# =========================
app = FastAPI(
    title="AEMET Forecast API",
    version="1.0.0"
)


@app.get("/")
def status():
    return {"status": "ok"}


# =========================
# ENDPOINT HISTÓRICO
# =========================
@app.get(
    "/temperaturas",
    response_model=list[TemperatureResponse]
)
def get_temperaturas(
    ubicacion: Optional[str] = None,
    limit: int = 7
):
    conn = get_connection()
    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    query = """
    SELECT
        data->>'numero_de_estacion'           AS numero_de_estacion,
        data->>'ubicacion_de_la_estacion'     AS ubicacion_de_la_estacion,
        data->>'fecha'                        AS fecha,
        (data->>'temperatura_maxima')::float  AS temperatura_maxima,
        (data->>'temperatura_minima')::float  AS temperatura_minima
    FROM observaciones
    """
    params = []

    if ubicacion:
        query += " WHERE data->>'ubicacion_de_la_estacion' = %s"
        params.append(ubicacion)

    query += " ORDER BY data->>'fecha' DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows


# =========================
# ENDPOINT FORECAST
# =========================
@app.post(
    "/forecast",
    response_model=list[PredictionResponse]
)
def forecast(req: ForecastRequest):
    dias = req.dias
    ubicacion = req.ubicacion

    # Cargar los modelos bajo demanda (no al inicio)
    model_tmax = load_model(MODEL_TMAX_KEY)
    model_tmin = load_model(MODEL_TMIN_KEY)

    # Crear features (día índice)
    X_future = pd.DataFrame({"dia": range(1, dias + 1)})

    tmax_preds = model_tmax.predict(X_future)
    tmin_preds = model_tmin.predict(X_future)

    results = []
    for i in range(dias):
        results.append({
            "dia": i + 1,
            "temperatura_maxima_predicha": float(tmax_preds[i]),
            "temperatura_minima_predicha": float(tmin_preds[i])
        })

    return results




