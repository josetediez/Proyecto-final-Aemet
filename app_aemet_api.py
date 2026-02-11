from fastapi import FastAPI, HTTPException, Query
import requests

app = FastAPI()

@app.post("/prediccion")
def prediccion(ciudad: str = Query(..., description="Ciudad de la cual quieres predecir la temperatura")):
    try:
        # Geocodificación
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

        # Clima diario 7 días
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

        # Generar gráfico ASCII simple
        grafico_ascii = []
        for max_t, min_t in zip(temp_max, temp_min):
            max_bar = "█" * max(0, int(round(max_t)))
            min_bar = "░" * max(0, int(round(min_t)))
            grafico_ascii.append(f"{max_bar}{min_bar}")

        return {
            "ciudad": ciudad,
            "latitud": lat,
            "longitud": lon,
            "fechas": dates,
            "temperatura_maxima": temp_max,
            "temperatura_minima": temp_min,
            "grafico_ascii": grafico_ascii
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")


@app.get("/clima_web")
def clima_actual(ciudad: str = Query(..., description="Ciudad de la cual quieres saber la temperatura actual")):
    try:
        # Geocodificación
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

        # Clima actual
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
            "ciudad": ciudad,
            "latitud": lat,
            "longitud": lon,
            "temperatura": current.get("temperature"),
            "velocidad_viento": current.get("windspeed"),
            "direccion_viento": current.get("winddirection"),
            "fecha_hora": current.get("time")
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")

