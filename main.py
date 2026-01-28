import pandas as pd
import os
from datetime import datetime, timezone, timedelta
from datetime import time as dt_time
import pytz
import json
import pickle
import re

SEED = 12345

basepath = os.path.dirname(os.path.realpath(__file__))
base = lambda p: os.path.join(basepath, p)

df = pd.read_csv(base("car_data.csv"))
df = df.drop_duplicates(subset=['Make', 'Model'], keep='first')
documents = df.to_dict("records")

# Filter out cars with zeros in any numeric column
def is_valid_car(car):
    numeric_columns = ["Year", "Horsepower"]
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

# Reset time for the "car of the day" (hour, minute) in EST
# Change this single value to control when the daily car rotates.
RESET_TIME = dt_time(0, 0)

EPOCH_START = datetime(2026, 1, 20, tzinfo=EST)

def get_current_day_number():
    now = datetime.now(EST)
    
    # Epoch's first reset at the configured reset time
    epoch_reset = EPOCH_START.replace(hour=RESET_TIME.hour, minute=RESET_TIME.minute, second=0, microsecond=0)
    
    # Calculate complete reset periods since epoch
    delta = now - epoch_reset
    days = delta.days
    
    # If we haven't reached today's reset time yet, we're still in yesterday's period
    today_reset = now.replace(hour=RESET_TIME.hour, minute=RESET_TIME.minute, second=0, microsecond=0)
    if now < today_reset:
        days -= 1
    
    return days + 2

def get_time_until_next_day():
    now = datetime.now(EST)
    next_reset = now.replace(hour=RESET_TIME.hour, minute=RESET_TIME.minute, second=0, microsecond=0)
    if next_reset <= now:
        next_reset += timedelta(days=1)
    delta = next_reset - now
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
    random.seed(day_number + SEED)
    
    shuffled = selectable_documents.copy()
    random.shuffle(shuffled)
    
    for car in shuffled:
        year = car.get("Year", "")
        name = f'"{car["Make"]} {car["Model"]}" {year}'
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
                    return car
    return None

cached = load_cached_car()
cache_loaded = cached is not None
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
random.seed(day_number + SEED)
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

# Function to delete the cache file
def delete_cache():
    cache_file = base("car_cache.pkl")
    if os.path.exists(cache_file):
        os.remove(cache_file)
        print(f"Cache file deleted at {datetime.now(EST)}")




# Ensure the cache on-demand: if the cached day doesn't match current day, remove and regenerate
def ensure_car_cache_current():
    global cached, cache_loaded, car, img, greyscale, width, height, clue, clue_variants, day_number
    cache_file = base("car_cache.pkl")
    # If cache exists but for a different day, delete it
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            if cached_data.get('day_number') != get_current_day_number():
                try:
                    os.remove(cache_file)
                    print(f"Stale cache removed at {datetime.now(EST)}")
                except Exception as e0:
                    print(e0)
                    pass
                cached = None
                cache_loaded = False
            else:
                # Load into globals if not already
                cached = cached_data
                cache_loaded = True
                car = cached['car']
                img = Image.open(BytesIO(cached['img_data']))
        except Exception as e1:
            print(e1)
            # Corrupt cache - delete it
            try:
                os.remove(cache_file)
            except Exception as e2:
                print(e2)
                pass
            cached = None
            cache_loaded = False

    # If no current cache, pick a car and save
    if not cache_loaded:
        car = chooseCar()
        response = requests.get(car["url"])
        img_data = response.content
        img = Image.open(BytesIO(img_data))
        try:
            save_car_cache(car, img_data)
        except Exception:
            pass

    # Recompute derived image/clue data
    greyscale = img.convert("L")
    width, height = greyscale.size
    day_number = get_current_day_number()
    random.seed(day_number + SEED)
    clue = greyscale.crop((random.randint(0, int(width*0.4)), random.randint(0, int(height*0.4)), int(width*0.6), int(height*0.6)))
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
    # Ensure cache is current for this request (deletes stale cache)
    ensure_car_cache_current()
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
    cars = [f"{doc['Make']} {doc['Model']}" for doc in selectable_documents]
    return cars

@app.get("/day-info")
async def get_day_info():
    return {
        "day_number": get_current_day_number(),
        "seconds_until_next": get_time_until_next_day(),
        "cache_loaded": cache_loaded
    }

@app.get("/car/{car_name}")
async def get_car_details(car_name: str):
    # Find the car in documents
    for doc in documents:
        full_name = f"{doc['Make']} {doc['Model']}"
        if full_name.lower() == car_name.lower():
            return {
                "make": doc["Make"],
                "model": doc["Model"],
                "year": safe_value(doc["Year"]),
                "cylinders": safe_value(doc["Cylinders"]),
                "horsepower": safe_value(doc["Horsepower"]),
                "fuel_capacity_gal": safe_value(doc["Fuel capacity (gal)"]),
                "fuel_capacity_liters": safe_value(doc["Fuel capacity (L)"]),
                "country": safe_value(doc["Country"])
            }
    return None

@app.post("/check-guess")
async def check_guess(guess: dict):
    guessed_car_name = guess.get("car_name", "").strip()
    
    # Find the guessed car in documents
    guessed_car = None
    for doc in documents:
        full_name = f"{doc['Make']} {doc['Model']}"
        if full_name.lower() == guessed_car_name.lower():
            guessed_car = doc
            break
    
    if not guessed_car:
        return {"error": "Car not found"}
    
    # Compare with correct car and return comparison results
    correct_name = f"{car['Make']} {car['Model']}"
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
                
                # For cylinders, extract numeric value after first character if needed
                if value_type == "cylinders":
                    # Extract just the number from values like "V6", "4", "V8", etc.
                    g_match = re.search(r'\d+', g_str)
                    c_match = re.search(r'\d+', c_str)
                    g_val = float(g_match.group(0)) if g_match else float(g_str)
                    c_val = float(c_match.group(0)) if c_match else float(c_str)
                else:
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
        "make": guessed_car["Make"],
        "make_correct": guessed_car["Make"].lower() == car["Make"].lower(),
        "comparisons": {
            "year": compare_value(safe_value(guessed_car["Year"]), safe_value(car["Year"]), "number"),
            "cylinders": compare_value(safe_value(guessed_car["Cylinders"]), safe_value(car["Cylinders"]), "cylinders"),
            "horsepower": compare_value(safe_value(guessed_car["Horsepower"]), safe_value(car["Horsepower"]), "number"),
            "fuel_capacity_gal": compare_value(safe_value(guessed_car["Fuel capacity (gal)"]), safe_value(car["Fuel capacity (gal)"]), "number"),
            "fuel_capacity_liters": compare_value(safe_value(guessed_car["Fuel capacity (L)"]), safe_value(car["Fuel capacity (L)"]), "number"),
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
        "cylinders": safe_value(car["Cylinders"]),
        "hp": safe_value(car["Horsepower"]),
        "fuel": f"{safe_value(car['Fuel capacity (gal)'])} / {safe_value(car['Fuel capacity (L)'])}",
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
        "name": f"{car['Make']} {car['Model']}"
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