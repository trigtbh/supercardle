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
    random.seed(day_number + 8473594379587439874)
    
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
random.seed(day_number + 58974398754398)
clue = greyscale.crop((random.randint(0, int(width*0.4)), random.randint(0, int(height*0.4)), int(width*0.6), int(height*0.6)))

# Maximum number of guesses (affects number of clue variants)
maxGuesses = 7

# Generate clue variants with progressive zoom and color
def create_clue_variants(original_img, clue_img, num_guesses=7):
    """Create progressive clue variants with zoom out and color reveal"""
    variants = []
    
    # Crop the original image to start at 50% visible area
    orig_width, orig_height = original_img.size
    crop_factor_orig = 0.5
    crop_width_orig = int(orig_width * crop_factor_orig)
    crop_height_orig = int(orig_height * crop_factor_orig)
    left_orig = (orig_width - crop_width_orig) // 2
    top_orig = (orig_height - crop_height_orig) // 2
    cropped_original = original_img.crop((left_orig, top_orig, left_orig + crop_width_orig, top_orig + crop_height_orig))
    
    # For each guess number (0-indexed), create a variant
    for guess_num in range(num_guesses):
        # Calculate crop size: guess 0 shows small portion (zoomed in), guess 6 shows full cropped original
        # Crop size factor from 0.5 (50% of cropped original) to 1.0 (full cropped original)
        crop_factor = 0.5 + (guess_num / (num_guesses - 1)) * 0.5  # 0.5 to 1.0
        
        # Get cropped original dimensions
        crop_orig_width, crop_orig_height = cropped_original.size
        
        # Calculate the crop area from the cropped original
        crop_width = int(crop_orig_width * crop_factor)
        crop_height = int(crop_orig_height * crop_factor)
        
        # Center the crop
        left = (crop_orig_width - crop_width) // 2
        top = (crop_orig_height - crop_height) // 2
        
        # Crop the image
        cropped = cropped_original.crop((left, top, left + crop_width, top + crop_height))
        
        # Scale back to original cropped size for display
        variant = cropped.resize((crop_orig_width, crop_orig_height), Image.Resampling.LANCZOS)
        
        # Apply color desaturation based on guess number
        # Guess 0: grayscale, Guess 6: full color
        color_intensity = guess_num / (num_guesses - 1)  # 0 to 1
        
        # Convert to RGB if needed
        variant_rgb = variant.convert("RGB")
        
        # Blend grayscale with color
        grayscale_variant = variant_rgb.convert("L")
        
        # Create color image by blending
        result = Image.new("RGB", variant_rgb.size)
        pixels_color = variant_rgb.load()
        pixels_gray = grayscale_variant.load()
        result_pixels = result.load()
        
        for y in range(variant_rgb.size[1]):
            for x in range(variant_rgb.size[0]):
                gray_val = pixels_gray[x, y]
                color_val = pixels_color[x, y]
                
                # Blend: grayscale to color based on intensity
                r = int(gray_val * (1 - color_intensity) + color_val[0] * color_intensity)
                g = int(gray_val * (1 - color_intensity) + color_val[1] * color_intensity)
                b = int(gray_val * (1 - color_intensity) + color_val[2] * color_intensity)
                
                result_pixels[x, y] = (r, g, b)
        
        variants.append(result)
    
    return variants

clue_variants = create_clue_variants(img, clue, maxGuesses)

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
async def get_clue(guess: int = 0):
    """Get clue image for a specific guess number (0-indexed)"""
    # Clamp guess to valid range
    guess = max(0, min(guess, len(clue_variants) - 1))
    
    img_byte_arr = BytesIO()
    clue_variants[guess].save(img_byte_arr, format='PNG')
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