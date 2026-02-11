from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()

class CiudadRequest(BaseModel):
    ciudad: str

@app.post("/clima_web")
def clima_web(req: CiudadRequest):
    try:
        # 1️⃣ Obtener latitud y longitud usando Nominatim (OpenStreetMap)
        geo_resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": req.ciudad, "format": "json", "limit": 1},
            timeout=10
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            raise HTTPException(status_code=404, detail="Ciudad no encontrada")
        
        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        # 2️⃣ Consultar Open-Meteo para obtener datos meteorológicos
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
            raise HTTPException(status_code=404, detail="No se pudo obtener el clima")

        current = weather_data["current_weather"]

        return {
            "ciudad": req.ciudad,
            "temperatura": current.get("temperature"),
            "velocidad_viento": current.get("windspeed"),
            "direccion_viento": current.get("winddirection"),
            "hora": current.get("time")
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")




