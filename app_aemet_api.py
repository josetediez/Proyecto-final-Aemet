from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()

class CiudadRequest(BaseModel):
    ciudad: str

@app.post("/clima_web")
def clima_web(req: CiudadRequest):
    try:
        # 1️⃣ Geocodificación con Open-Meteo
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

        # 2️⃣ Clima actual con Open-Meteo
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True
            },
            timeout=10
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

        if "current_weather" not in weather_data:
            raise HTTPException(status_code=500, detail="No se pudo obtener el clima actual")

        current = weather_data["current_weather"]

        return {
            "ciudad": req.ciudad,
            "latitud": lat,
            "longitud": lon,
            "temperatura": current.get("temperature"),
            "velocidad_viento": current.get("windspeed"),
            "direccion_viento": current.get("winddirection"),
            "fecha_hora": current.get("time")
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")






