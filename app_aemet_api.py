import os
import io
import boto3
import joblib
import psycopg2
import psycopg2.extras
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional


# =========================
# CONFIGURACIÓN BD
# =========================
DB_HOST = os.environ.get("DB_HOST", "datosaemet.c16uosue6hjy.eu-north-1.rds.amazonaws.com")
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
# MODELOS ML (S3)
# =========================
BUCKET_MODELOS = "modelos-forecasting"
MODEL_TMAX_KEY = "model_tmax.pkl"
MODEL_TMIN_KEY = "model_tmin.pkl"

s3 = boto3.client("s3")
model_tmax = None
model_tmin = None


def load_models_once():
    global model_tmax, model_tmin
    if model_tmax is None:
        obj = s3.get_object(Bucket=BUCKET_MODELOS, Key=MODEL_TMAX_KEY)
        model_tmax = joblib.load(io.BytesIO(obj["Body"].read()))
    if model_tmin is None:
        obj = s3.get_object(Bucket=BUCKET_MODELOS, Key=MODEL_TMIN_KEY)
        model_tmin = joblib.load(io.BytesIO(obj["Body"].read()))


# =========================
# Pydantic
# =========================
class TemperatureResponse(BaseModel):
    numero_de_estacion: str
    ubicacion_de_la_estacion: str
    fecha: str
    temperatura_maxima: Optional[float]
    temperatura_minima: Optional[float]


class TemperatureQuery(BaseModel):
    ubicacion: Optional[str] = None
    limit: int = 7

    class Config:
        schema_extra = {
            "example": {
                "ubicacion": "Sopuerta",
                "limit": 7
            }
        }


class ForecastRequest(BaseModel):
    ubicacion: str
    dias: int

    class Config:
        schema_extra = {
            "example": {
                "ubicacion": "Sopuerta",
                "dias": 5
            }
        }


class PredictionResponse(BaseModel):
    dia: int
    temperatura_maxima_predicha: float
    temperatura_minima_predicha: float


class GeminiRequest(BaseModel):
    ubicacion: str  # ahora pedimos ubicación en lugar de estación
    fecha: Optional[str] = None  # formato YYYY-MM-DD

    class Config:
        schema_extra = {
            "example": {
                "ubicacion": "Bilbao",
                "fecha": "2026-02-10"
            }
        }


class GeminiResponse(BaseModel):
    estacion: str
    fecha: str
    temperatura_maxima: Optional[float]
    temperatura_minima: Optional[float]
    humedad_relativa: Optional[float]
    presion_atmosferica: Optional[float]


# =========================
# FASTAPI
# =========================
app = FastAPI(title="AEMET Forecast API", version="1.0.0")

AEMET_API_KEY = os.environ.get("AEMET_API_KEY")
AEMET_URL = "https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/{estacion}/"


@app.get("/")
def status():
    return {"status": "ok"}


# =========================
# ENDPOINT HISTÓRICO
# =========================
@app.get("/temperaturas", response_model=List[TemperatureResponse])
def get_temperaturas(ubicacion: Optional[str] = None, limit: int = 7):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
    SELECT
        numero_de_estacion,
        ubicacion_de_la_estacion,
        fecha,
        temperatura_maxima,
        temperatura_minima
    FROM observaciones
    """
    params = []
    if ubicacion:
        query += " WHERE ubicacion_de_la_estacion = %s"
        params.append(ubicacion)
    query += " ORDER BY fecha DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows


# =========================
# ENDPOINT FORECAST
# =========================
@app.post("/forecast", response_model=List[PredictionResponse])
def forecast(req: ForecastRequest):
    load_models_once()
    dias = req.dias
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


# =========================
# ENDPOINT PREGÚNTALE A GEMINI
# =========================
@app.post("/preguntale_a_gemini", response_model=GeminiResponse)
def preguntale_a_gemini(req: GeminiRequest):
    if not AEMET_API_KEY:
        raise HTTPException(status_code=500, detail="Falta API key de AEMET")

    headers = {"api_key": AEMET_API_KEY}

    # 1️⃣ Buscar la estación correspondiente a la ubicación
    estaciones_url = "https://opendata.aemet.es/opendata/api/valores/climatologicos/inventarioestaciones/todas/"
    try:
        r = requests.get(estaciones_url, headers=headers, timeout=10)
        r.raise_for_status()
        estaciones_meta_url = r.json().get("datos")

        r2 = requests.get(estaciones_meta_url, timeout=10)
        r2.raise_for_status()
        estaciones = r2.json()

        # Filtrar por ubicación
        estaciones_filtradas = [e for e in estaciones if req.ubicacion.lower() in e.get("nombre").lower()]
        if not estaciones_filtradas:
            raise HTTPException(status_code=404, detail="No se encontró estación para esa ubicación")

        estacion_codigo = estaciones_filtradas[0]["indicativo"]

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 2️⃣ Obtener los datos de la estación
    url = AEMET_URL.format(estacion=estacion_codigo)
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        datos_url = r.json().get("datos")
        if not datos_url:
            raise HTTPException(status_code=404, detail="No se encontraron datos de la estación")

        r2 = requests.get(datos_url, timeout=10)
        r2.raise_for_status()
        datos = r2.json()

        # Filtrar por fecha si se pasa
        if req.fecha:
            datos = [d for d in datos if d.get("fecha") == req.fecha]
            if not datos:
                raise HTTPException(status_code=404, detail="No hay datos para esa fecha")

        ultimo = datos[-1]

        return GeminiResponse(
            estacion=estacion_codigo,
            fecha=ultimo.get("fecha"),
            temperatura_maxima=ultimo.get("ta_max"),
            temperatura_minima=ultimo.get("ta_min"),
            humedad_relativa=ultimo.get("hr"),
            presion_atmosferica=ultimo.get("pres_max")
        )

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
