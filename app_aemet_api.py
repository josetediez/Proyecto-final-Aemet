from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from io import BytesIO
import base64
import matplotlib.pyplot as plt

app = FastAPI()

class CiudadRequest(BaseModel):
    ciudad: str

@app.post("/clima_web")
def clima_web(req: CiudadRequest):
    try:
        # Geocodificación con Open-Meteo
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": req.ciudad, "count": 1},
            timeout=10
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        if "results" not in geo_data or len(geo_data["results"]) == 0:
            raise HTTPException(status_code=404, detail=f"No se encontró la ciudad '{req.ciudad}'")

        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]

        # Clima actual + predicción diaria 7 días
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 7
            },
            timeout=10
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

        if "daily" not in weather_data:
            raise HTTPException(status_code=500, detail="No se pudo obtener el clima")

        daily = weather_data["daily"]
        dates = daily["time"]
        temp_max = daily["temperature_2m_max"]
        temp_min = daily["temperature_2m_min"]

        # Generar gráfico
        plt.figure(figsize=(8,4))
        plt.plot(dates, temp_max, marker='o', label="Temp. Máx")
        plt.plot(dates, temp_min, marker='o', label="Temp. Mín")
        plt.fill_between(dates, temp_min, temp_max, color='orange', alpha=0.1)
        plt.xlabel("Fecha")
        plt.ylabel("Temperatura (°C)")
        plt.title(f"Pronóstico de temperatura para {req.ciudad}")
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Convertir gráfico a base64
        buf = BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")

        return {
            "ciudad": req.ciudad,
            "latitud": lat,
            "longitud": lon,
            "fechas": dates,
            "temperatura_maxima": temp_max,
            "temperatura_minima": temp_min,
            "grafico_base64": img_base64
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")
