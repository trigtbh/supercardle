import pandas as pd
import os
from datetime import datetime, timezone, timedelta
import pytz
import json
import pickle

basepath = os.path.dirname(os.path.realpath(__file__))
base = lambda p: os.path.join(basepath, p)

df = pd.read_csv(base("cars.csv"))
df = df.drop_duplicates(subset=['Car Make', 'Car Model'], keep='first')
documents = df.to_dict("records")

# Filter out electric cars and cars with zeros in any column
def is_valid_car(car):
    # Check if engine size is numeric (not electric)
    engine_size = car.get("Engine Size (L)")
    if engine_size is None:
        return False
    
    try:
        engine_val = float(engine_size)
        if engine_val == 0:
            return False
    except (ValueError, TypeError):
        return False
    
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

selectable_documents = [car for car in documents if is_valid_car(car)]

import random
from PIL import Image
import requests
from io import BytesIO

EST = pytz.timezone('America/New_York')

EPOCH_START = datetime(2026, 1, 20, tzinfo=EST)

def get_current_day_number():
    now = datetime.now(EST)
    delta = now - EPOCH_START
    return delta.days + 1

def get_time_until_next_day():
    now = datetime.now(EST)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = next_midnight - now
    return int(delta.total_seconds())

def load_cached_car():
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
        year = car.get("Year", "")
        name = f'"{car["Car Make"]} {car["Car Model"]}" {year}'
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

@app.post("/check-guess")
async def check_guess(guess: dict):
    guessed_car_name = guess.get("car_name", "").strip()
    
    # Find the guessed car in documents
    guessed_car = None
    for doc in documents:
        full_name = f"{doc['Car Make']} {doc['Car Model']}"
        if full_name.lower() == guessed_car_name.lower():
            guessed_car = doc
            break
    
    if not guessed_car:
        return {"error": "Car not found"}
    
    # Compare with correct car and return comparison results
    correct_name = f"{car['Car Make']} {car['Car Model']}"
    is_correct = guessed_car_name.lower() == correct_name.lower()
    
    def compare_value(guessed, correct, value_type):
        if guessed is None or correct is None:
            return {"status": "unknown", "value": guessed}
        
        if value_type == "string":
            return {
                "status": "correct" if str(guessed).lower() == str(correct).lower() else "incorrect",
                "value": guessed
            }
        else:  # numeric comparison
            try:
                # Remove commas from strings before converting to float
                g_str = str(guessed).replace(',', '')
                c_str = str(correct).replace(',', '')
                g_val = float(g_str)
                c_val = float(c_str)
                if g_val == c_val:
                    status = "correct"
                elif g_val < c_val:
                    status = "lower"
                else:
                    status = "higher"
                return {"status": status, "value": guessed}
            except (ValueError, TypeError):
                return {"status": "unknown", "value": guessed}
    
    return {
        "is_correct": is_correct,
        "make": guessed_car["Car Make"],
        "make_correct": guessed_car["Car Make"].lower() == car["Car Make"].lower(),
        "comparisons": {
            "year": compare_value(safe_value(guessed_car["Year"]), safe_value(car["Year"]), "number"),
            "engine_size": compare_value(safe_value(guessed_car["Engine Size (L)"]), safe_value(car["Engine Size (L)"]), "number"),
            "horsepower": compare_value(safe_value(guessed_car["Horsepower"]), safe_value(car["Horsepower"]), "number"),
            "torque": compare_value(safe_value(guessed_car["Torque (lb-ft)"]), safe_value(car["Torque (lb-ft)"]), "number"),
            "price": compare_value(safe_value(guessed_car["Price (in USD)"]), safe_value(car["Price (in USD)"]), "number"),
            "country": compare_value(safe_value(guessed_car["Country"]), safe_value(car["Country"]), "string")
        },
        "correct_name": correct_name if is_correct else None  # Only reveal name if guess is correct
    }

@app.post("/reveal-hint")
async def reveal_hint(request: dict):
    """Reveal a specific column value as a hint"""
    column_name = request.get("column_name", "").strip().lower()
    
    column_map = {
        "year": safe_value(car["Year"]),
        "engine": safe_value(car["Engine Size (L)"]),
        "hp": safe_value(car["Horsepower"]),
        "torque": safe_value(car["Torque (lb-ft)"]),
        "price": safe_value(car["Price (in USD)"]),
        "country": safe_value(car["Country"])
    }
    
    if column_name not in column_map:
        return {"error": "Invalid column name"}
    
    return {
        "column": column_name,
        "value": column_map[column_name]
    }

@app.post("/reveal-answer")
async def reveal_answer():
    """Reveal the correct car name (for game over)"""
    return {
        "name": f"{car['Car Make']} {car['Car Model']}"
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