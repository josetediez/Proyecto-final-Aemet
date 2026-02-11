from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from datetime import datetime

app = FastAPI()

class ClimaRequest(BaseModel):
    ciudad: str
    fecha: str  # formato YYYY-MM-DD

@app.post("/clima_web")
def clima_web(req: ClimaRequest):
    try:
        # Validar formato de fecha
        try:
            fecha_obj = datetime.strptime(req.fecha, "%Y-%m-%d")
            fecha_str = fecha_obj.strftime("%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="La fecha debe estar en formato YYYY-MM-DD")

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

        # Clima histórico con Open-Meteo
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum",
                "start_date": fecha_str,
                "end_date": fecha_str,
                "timezone": "auto"
            },
            timeout=10
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

        if "daily" not in weather_data:
            raise HTTPException(status_code=500, detail="No se pudo obtener el clima para esa fecha")

        daily = weather_data["daily"]

        return {
            "ciudad": req.ciudad,
            "fecha": fecha_str,
            "temperatura_maxima": daily.get("temperature_2m_max", [None])[0],
            "temperatura_minima": daily.get("temperature_2m_min", [None])[0],
            "temperatura_aparente_max": daily.get("apparent_temperature_max", [None])[0],
            "temperatura_aparente_min": daily.get("apparent_temperature_min", [None])[0],
            "precipitacion": daily.get("precipitation_sum", [None])[0]
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")
