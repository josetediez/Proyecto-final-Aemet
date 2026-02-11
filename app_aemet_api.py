from fastapi import FastAPI, HTTPException, Query
from datetime import datetime
import requests
from meteostat import Point, Daily
import pandas as pd

app = FastAPI()

@app.get("/clima_historico")
def clima_historico(
    ciudad: str = Query(..., description="Ciudad de la cual quieres saber la temperatura"),
    fecha: str = Query(..., description="Fecha en formato YYYY-MM-DD")
):
    try:
        # Validar fecha
        try:
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa YYYY-MM-DD")

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

        # Datos históricos con Meteostat
        location = Point(lat, lon)
        data = Daily(location, fecha_dt, fecha_dt)
        data = data.fetch()

        if data.empty:
            raise HTTPException(status_code=404, detail=f"No hay datos meteorológicos para {ciudad} en {fecha}")

        # Tomamos la primera fila (solo un día)
        row = data.iloc[0]

        return {
            "ciudad": ciudad,
            "fecha": fecha,
            "temperatura_maxima": row["tmax"],
            "temperatura_minima": row["tmin"],
            "precipitacion": row["prcp"],
            "velocidad_viento": row["wspd"],
            "direccion_viento": row["wdir"]
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener la geolocalización: {e}")
