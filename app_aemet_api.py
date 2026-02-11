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
# MODELOS PYDANTIC
# =========================

class TemperatureResponse(BaseModel):
    numero_de_estacion: str
    ubicacion_de_la_estacion: str
    fecha: str
    temperatura_maxima: Optional[float]
    temperatura_minima: Optional[float]
    direccion_media_del_aire: Optional[float]
    humedad_relativa: Optional[float]
    presion_atmosferica_minima: Optional[float]
    presion_atmosferica_maxima: Optional[float]

class ForecastRequest(BaseModel):
    ubicacion: str
    dias: int

class PredictionResponse(BaseModel):
    dia: int
    temperatura_maxima_predicha: float
    temperatura_minima_predicha: float

class GeminiRequest(BaseModel):
    estacion: str
    fecha: Optional[str] = None

class GeminiResponse(BaseModel):
    estacion: str
    fecha: str
    temperatura_maxima: Optional[float]
    temperatura_minima: Optional[float]
    humedad_relativa: Optional[float]
    presion_atmosferica: Optional[float]

# =========================
# FASTAPI APP
# =========================

app = FastAPI(title="AEMET API", version="1.0.0")

AEMET_API_KEY = os.environ.get("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb3NldGVkaWV6QGdtYWlsLmNvbSIsImp0aSI6IjMyZTE3MTQ4LWExYmQtNDY1OS1hMDlmLTMyMDhiNjQzZTcxZCIsImlzcyI6IkFFTUVUIiwiaWF0IjoxNzYxMjM0MTU4LCJ1c2VySWQiOiIzMmUxNzE0OC1hMWJkLTQ2NTktYTA5Zi0zMjA4YjY0M2U3MWQiLCJyb2xlIjoiIn0.U4LALv8ROVsg87pDNiAXU6Ba1ANIQM1M-6VWbuOMx8s")  
AEMET_URL = "https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/{estacion}/"

@app.get("/")
def status():
    return {"status": "Api arrancada"}

# =========================
# ENDPOINT HISTÓRICO
# =========================

@app.get("/temperaturas", response_model=List[TemperatureResponse])
def get_temperaturas(ubicacion: Optional[str] = None, limit: int = 7):
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
        SELECT
            numero_de_estacion,
            ubicacion_de_la_estacion,
            fecha,
            temperatura_maxima,
            temperatura_minima,
            direccion_media_del_aire,
            humedad_relativa,
            presion_atmosferica_minima,
            presion_atmosferica_maxima
        FROM datosaemet.observaciones
        """
        params = []
        if ubicacion:
            query += " WHERE LOWER(ubicacion_de_la_estacion) = LOWER(%s)"
            params.append(ubicacion)
        query += " ORDER BY fecha DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        # Convertir fechas a string y Decimal a float
        for row in rows:
            row['fecha'] = row['fecha'].isoformat() if row['fecha'] else None
            for col in ['temperatura_maxima', 'temperatura_minima', 
                        'direccion_media_del_aire', 'humedad_relativa',
                        'presion_atmosferica_minima', 'presion_atmosferica_maxima']:
                if row[col] is not None:
                    row[col] = float(row[col])

        return rows

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

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

from typing import Optional
from fastapi import HTTPException

@app.post("/preguntale_a_gemini")
def preguntale_a_gemini(req: Optional[GeminiRequest] = None):

    if not AEMET_API_KEY:
        raise HTTPException(status_code=500, detail="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb3NldGVkaWV6QGdtYWlsLmNvbSIsImp0aSI6IjMyZTE3MTQ4LWExYmQtNDY1OS1hMDlmLTMyMDhiNjQzZTcxZCIsImlzcyI6IkFFTUVUIiwiaWF0IjoxNzYxMjM0MTU4LCJ1c2VySWQiOiIzMmUxNzE0OC1hMWJkLTQ2NTktYTA5Zi0zMjA4YjY0M2U3MWQiLCJyb2xlIjoiIn0.U4LALv8ROVsg87pDNiAXU6Ba1ANIQM1M-6VWbuOMx8s")

    estacion = req.estacion if req and req.estacion else "barcelona"
    fecha = req.fecha if req and req.fecha else None

    headers = {"api_key": AEMET_API_KEY}
    url = AEMET_URL.format(estacion=estacion)

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        json_meta = r.json()

        datos_url = json_meta.get("datos")
        if not datos_url:
            raise HTTPException(status_code=404, detail="No se encontraron datos")

        r2 = requests.get(datos_url, timeout=10)
        r2.raise_for_status()
        datos = r2.json()

        if fecha:
            datos = [d for d in datos if d.get("fecha") == fecha]
            if not datos:
                raise HTTPException(status_code=404, detail="No hay datos para esa fecha")

        ultimo = datos[-1]

        return {
            "estacion": estacion,
            "fecha": ultimo.get("fecha"),
            "temperatura_maxima": ultimo.get("ta_max"),
            "temperatura_minima": ultimo.get("ta_min"),
            "humedad_relativa": ultimo.get("hr"),
            "presion_atmosferica": ultimo.get("pres_max")
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

