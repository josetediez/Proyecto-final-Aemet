from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI(title="Clima Web")

class ClimaRequest(BaseModel):
    ciudad: str

@app.post("/clima_web")
def clima_web(req: ClimaRequest):
    if not req.ciudad:
        raise HTTPException(status_code=400, detail="Debes indicar una ciudad")
    
    url = f"https://wttr.in/{req.ciudad}?format=j1"  # JSON de wttr.in
    
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        datos = r.json()
        
        # Tomamos el clima actual
        current = datos.get("current_condition", [{}])[0]
        
        return {
            "ciudad": req.ciudad,
            "temperatura_C": current.get("temp_C"),
            "temperatura_F": current.get("temp_F"),
            "humedad": current.get("humidity"),
            "viento_kmph": current.get("windspeedKmph"),
            "descripcion": current.get("weatherDesc", [{}])[0].get("value")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo obtener el clima: {e}")


