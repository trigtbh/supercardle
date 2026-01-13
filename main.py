import pandas as pd
import os

basepath = os.path.dirname(os.path.realpath(__file__))
base = lambda p: os.path.join(basepath, p)

df = pd.read_csv(base("cars.csv"))
documents = df.to_dict("records")

import random
from PIL import Image
import requests
from io import BytesIO

def chooseCar() -> dict:

    r = None
    car = None

    while r is None and car is None:
        car = random.choice(documents)
        name = car["Car Make"] + " " + car["Car Model"]
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = ddgs.images(name, max_results=1)
            for result in results:
                r = result["image"]
        if r:
            car["url"] = r
            break

    assert car is not None  # linter screams if you comment out this line >:(
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

@app.get("/clue.png")
async def get_clue():
    img_byte_arr = BytesIO()
    clue.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)