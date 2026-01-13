import pandas as pd
import os
from datetime import datetime, timezone, timedelta
import pytz
import json
import pickle

basepath = os.path.dirname(os.path.realpath(__file__))
base = lambda p: os.path.join(basepath, p)

df = pd.read_csv(base("cars.csv"))
# Remove duplicates based on Car Make and Car Model
df = df.drop_duplicates(subset=['Car Make', 'Car Model'], keep='first')
documents = df.to_dict("records")

# Filter out electric cars and cars with zeros in any column
def is_valid_car(car):
    # Check if engine size is numeric (not electric)
    engine_size = car.get("Engine Size (L)")
    if engine_size is None:
        return False
    
    # Check if engine size is numeric
    try:
        engine_val = float(engine_size)
        if engine_val == 0:
            return False
    except (ValueError, TypeError):
        # Non-numeric engine size (e.g., "Electric")
        return False
    
    # Check for zeros in other numeric columns
    numeric_columns = ["Year", "Horsepower", "Torque (lb-ft)"]
    for col in numeric_columns:
        val = car.get(col)
        if val is not None:
            try:
                if float(val) == 0:
                    return False
            except (ValueError, TypeError):
                pass
    
    return True

# Filter documents to only include valid cars for selection
selectable_documents = [car for car in documents if is_valid_car(car)]

import random
from PIL import Image
import requests
from io import BytesIO

# Define EST timezone
EST = pytz.timezone('America/New_York')

EPOCH_START = datetime(2026, 1, 20, tzinfo=EST)

def get_current_day_number():
    """Get the current day number since epoch"""
    now = datetime.now(EST)
    delta = now - EPOCH_START
    return delta.days + 1

def get_time_until_next_day():
    """Get seconds until next midnight EST"""
    now = datetime.now(EST)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = next_midnight - now
    return int(delta.total_seconds())

def load_cached_car():
    """Load cached car data if it exists and is for today"""
    cache_file = base("car_cache.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                if cached_data['day_number'] == get_current_day_number():
                    return cached_data
        except:
            pass
    return None

def save_car_cache(car_data, img_data):
    """Save car data to cache"""
    cache_file = base("car_cache.pkl")
    cache_data = {
        'day_number': get_current_day_number(),
        'car': car_data,
        'img_data': img_data
    }
    with open(cache_file, 'wb') as f:
        pickle.dump(cache_data, f)

def chooseCar() -> dict:
    day_number = get_current_day_number()
    random.seed(day_number)
    
    r = None
    car = None

    while r is None or car is None:
        car = random.choice(selectable_documents)
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

# Try to load from cache first
cached = load_cached_car()
if cached:
    car = cached['car']
    img = Image.open(BytesIO(cached['img_data']))
else:
    car = chooseCar()
    response = requests.get(car["url"])
    img_data = response.content
    img = Image.open(BytesIO(img_data))
    save_car_cache(car, img_data)

greyscale = img.convert("L")
width, height = greyscale.size

day_number = get_current_day_number()
random.seed(day_number + 1000)
clue = greyscale.crop((random.randint(0, int(width*0.4)), random.randint(0, int(height*0.4)), int(width*0.6), int(height*0.6)))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from io import BytesIO
import math

def safe_value(val):
    if isinstance(val, float) and math.isnan(val):
        return None
    return val

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
    cars = [f"{doc['Car Make']} {doc['Car Model']}" for doc in selectable_documents]
    return cars

@app.get("/day-info")
async def get_day_info():
    return {
        "day_number": get_current_day_number(),
        "seconds_until_next": get_time_until_next_day()
    }

@app.get("/car/{car_name}")
async def get_car_details(car_name: str):
    # Find the car in documents
    for doc in documents:
        full_name = f"{doc['Car Make']} {doc['Car Model']}"
        if full_name.lower() == car_name.lower():
            return {
                "make": doc["Car Make"],
                "model": doc["Car Model"],
                "year": safe_value(doc["Year"]),
                "engine_size": safe_value(doc["Engine Size (L)"]),
                "horsepower": safe_value(doc["Horsepower"]),
                "torque": safe_value(doc["Torque (lb-ft)"]),
                "price": safe_value(doc["Price (in USD)"]),
                "country": safe_value(doc["Country"])
            }
    return None

@app.get("/correct-car")
async def get_correct_car():
    return {
        "name": f"{car['Car Make']} {car['Car Model']}",
        "make": car["Car Make"],
        "year": safe_value(car["Year"]),
        "engine_size": safe_value(car["Engine Size (L)"]),
        "horsepower": safe_value(car["Horsepower"]),
        "torque": safe_value(car["Torque (lb-ft)"]),
        "price": safe_value(car["Price (in USD)"]),
        "country": safe_value(car["Country"])
    }

@app.get("/clue.png")
async def get_clue():
    img_byte_arr = BytesIO()
    clue.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

@app.get("/full-image.png")
async def get_full_image():
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)