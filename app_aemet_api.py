from fastapi import FastAPI, HTTPException, Query
import requests

app = FastAPI()

@app.get("/clima_web")
def clima_web(
    ciudad: str = Query(..., description="Ciudad de la cual quieres saber la temperatura"),
    fecha: str = Query(..., description="Fecha en formato YYYY-MM-DD")
):
    try:
        # Geocodificación con Open-Meteo
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ciudad, "count": 1},
            timeout=10
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        if "results" not in geo_data or len(geo_data["results"]) == 0:
            raise HTTPException(status_code=404, detail=f"No se encontró la ciudad '{ciudad}'")

        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]

        # Clima para la fecha especificada con Open-Meteo
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum",
                "start_date": fecha,
                "end_date": fecha,
                "timezone": "auto"
            },
            timeout=10
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

        if "daily" not in weather_data or not weather_data["daily"].get("temperature_2m_max"):
            raise HTTPException(status_code=404, detail=f"No hay datos para la fecha {fecha}")

        daily = weather_data["daily"]

        return {
            "ciudad": ciudad,
            "latitud": lat,
            "longitud": lon,
            "fecha": fecha,
            "temperatura_maxima": daily["temperature_2m_max"][0],
            "temperatura_minima": daily["temperature_2m_min"][0],
            "temperatura_aparente_max": daily["apparent_temperature_max"][0],
            "temperatura_aparente_min": daily["apparent_temperature_min"][0],
            "precipitacion": daily["precipitation_sum"][0]
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")
