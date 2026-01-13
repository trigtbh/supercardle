import pandas as pd
import os

basepath = os.path.dirname(os.path.realpath(__file__))
base = lambda p: os.path.join(basepath, p)

df = pd.read_csv(base("cars.csv"))
# Remove duplicates based on Car Make and Car Model
df = df.drop_duplicates(subset=['Car Make', 'Car Model'], keep='first')
documents = df.to_dict("records")

import random
from PIL import Image
import requests
from io import BytesIO

def chooseCar() -> dict:

    r = None
    car = None

    while r is None or car is None:
        car = random.choice(documents)
        name = car["Car Make"] + " " + car["Car Model"]
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = ddgs.images(name, max_results=1)
            for result in results:
                r = result["image"]
                try:
                    Image.open(BytesIO(requests.get(r).content))
                except:
                    r = None
        if r:
            car["url"] = r
            break

    return car

car = chooseCar()
response = requests.get(car["url"])
img = Image.open(BytesIO(response.content))
greyscale = img.convert("L")
width, height = greyscale.size
clue = greyscale.crop((random.randint(0, int(width*0.4)), random.randint(0, int(height*0.4)), int(width*0.6), int(height*0.6)))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from io import BytesIO

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open(base("index.html"), "r") as f:
        return f.read()

@app.get("/index.css")
async def get_css():
    return FileResponse(base("index.css"))

@app.get("/script.js")
async def get_script():
    return FileResponse(base("script.js"))

@app.get("/cars")
async def get_cars():
    cars = [f"{doc['Car Make']} {doc['Car Model']}" for doc in documents]
    return cars

@app.get("/car/{car_name}")
async def get_car_details(car_name: str):
    # Find the car in documents
    for doc in documents:
        full_name = f"{doc['Car Make']} {doc['Car Model']}"
        if full_name.lower() == car_name.lower():
            return {
                "year": doc["Year"],
                "engine_size": doc["Engine Size (L)"],
                "horsepower": doc["Horsepower"],
                "torque": doc["Torque (lb-ft)"],
                "price": doc["Price (in USD)"],
                "country": doc["Country"]
            }
    return None

@app.get("/correct-car")
async def get_correct_car():
    return {
        "name": f"{car['Car Make']} {car['Car Model']}",
        "make": car["Car Make"],
        "year": car["Year"],
        "engine_size": car["Engine Size (L)"],
        "horsepower": car["Horsepower"],
        "torque": car["Torque (lb-ft)"],
        "price": car["Price (in USD)"],
        "country": car["Country"]
    }

@app.get("/clue.png")
async def get_clue():
    img_byte_arr = BytesIO()
    clue.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)