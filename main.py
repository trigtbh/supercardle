import logging
import pandas as pd
import os
from datetime import datetime, timezone, timedelta
from datetime import time as dt_time
import pytz
import json
import pickle
import re
logger = logging.getLogger(__name__)

SEED = 12345

# Maximum number of guesses (affects number of clue variants)
maxGuesses = 7

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
    print("LOG: load_cached_car() started")
    cache_file = base("car_cache.pkl")
    print(f"LOG: Checking cache file: {cache_file}")
    if os.path.exists(cache_file):
        print("LOG: Cache file exists")
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            print(f"LOG: Loaded data, cached day: {cached_data.get('day_number')}, current day: {get_current_day_number()}")
            if cached_data['day_number'] == get_current_day_number():
                print("LOG: Cache is valid")
                return cached_data
            else:
                print("LOG: Cache is for different day")
        except Exception as e:
            print(f"LOG: Error loading cache: {e}")
            pass
    else:
        print("LOG: Cache file does not exist")
    print("LOG: load_cached_car() returning None")
    return None

def save_car_cache(car_data, img_data, clue_variants_data):
    print("LOG: save_car_cache() started")
    cache_file = base("car_cache.pkl")
    cache_data = {
        'day_number': get_current_day_number(),
        'car': car_data,
        'img_data': img_data,
        'clue_variants': clue_variants_data
    }
    print(f"LOG: Saving cache to {cache_file}")
    with open(cache_file, 'wb') as f:
        pickle.dump(cache_data, f)
    print("LOG: Cache saved")

def chooseCar() -> dict:
    print("LOG: chooseCar() started")
    day_number = get_current_day_number()
    print(f"LOG: Day number: {day_number}")
    random.seed(day_number + SEED)
    print("LOG: Random seed set")
    
    shuffled = selectable_documents.copy()
    print(f"LOG: Shuffling {len(shuffled)} cars")
    random.shuffle(shuffled)
    
    for i, car in enumerate(shuffled):
        year = car.get("Year", "")
        name = f'"{car["Make"]} {car["Model"]}" {year}'
        print(f"LOG: Trying car {i+1}: {name}")
        from ddgs import DDGS
        with DDGS() as ddgs:
            print("LOG: Searching images")
            results = ddgs.images(name, max_results=1)
            print(f"LOG: Got {len(results)} results")
            for result in results:
                r = result["image"]
                print(f"LOG: Checking image URL: {r}")
                try:
                    print("LOG: Fetching image to verify")
                    Image.open(BytesIO(requests.get(r).content))
                    print("LOG: Image is valid")
                except Exception as e:
                    print(f"LOG: Image invalid: {e}")
                    r = None
                if r:
                    car["url"] = r
                    print(f"LOG: Selected car: {car['Make']} {car['Model']}")
                    return car
    print("LOG: No valid car found")
    return None

# Generate clue variants with progressive zoom and color
def create_clue_variants(original_img, clue_img, num_guesses=7):
    """Create progressive clue variants with zoom out and color reveal"""
    print(f"LOG: create_clue_variants() started with {num_guesses} guesses")
    variants = []
    
    # Crop the original image to start at 50% visible area
    orig_width, orig_height = original_img.size
    print(f"LOG: Original image size: {orig_width}x{orig_height}")
    crop_factor_orig = 0.5
    crop_width_orig = int(orig_width * crop_factor_orig)
    crop_height_orig = int(orig_height * crop_factor_orig)
    left_orig = (orig_width - crop_width_orig) // 2
    top_orig = (orig_height - crop_height_orig) // 2
    print("LOG: Cropping original to 50%")
    cropped_original = original_img.crop((left_orig, top_orig, left_orig + crop_width_orig, top_orig + crop_height_orig))
    
    # For each guess number (0-indexed), create a variant
    for guess_num in range(num_guesses):
        print(f"LOG: Creating variant for guess {guess_num}")
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
        print("LOG: Cropping variant")
        cropped = cropped_original.crop((left, top, left + crop_width, top + crop_height))
        
        # Scale back to original cropped size for display
        print("LOG: Resizing variant")
        variant = cropped.resize((crop_orig_width, crop_orig_height), Image.Resampling.LANCZOS)
        
        # Apply color desaturation based on guess number
        # Guess 0: grayscale, Guess 6: full color
        color_intensity = guess_num / (num_guesses - 1)  # 0 to 1
        print(f"LOG: Applying color intensity {color_intensity}")
        
        # Convert to RGB if needed
        variant_rgb = variant.convert("RGB")
        
        # Blend grayscale with color
        grayscale_variant = variant_rgb.convert("L")
        
        # Create color image by blending
        result = Image.new("RGB", variant_rgb.size)
        pixels_color = variant_rgb.load()
        pixels_gray = grayscale_variant.load()
        result_pixels = result.load()
        
        print("LOG: Blending pixels")
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
        print(f"LOG: Variant {guess_num} created")
    
    print("LOG: create_clue_variants() completed")
    return variants

# Global variables for caching
cached = None
cache_loaded = False
clue_variants_loaded = False
car = None
img = None
greyscale = None
width = None
height = None
clue = None
clue_variants = None
day_number = None

# Load cache on startup if available
print("LOG: Starting initial cache load on startup")
cached = load_cached_car()
print(f"LOG: load_cached_car() returned: {cached is not None}")
if cached:
    print("LOG: Cache found, loading into globals")
    cache_loaded = True
    car = cached['car']
    print(f"LOG: Loaded car: {car.get('Make')} {car.get('Model')}")
    img = Image.open(BytesIO(cached['img_data']))
    print("LOG: Loaded image from cache")
    if 'clue_variants' in cached:
        clue_variants = cached['clue_variants']
        clue_variants_loaded = True
        print("LOG: Loaded clue_variants from cache")
    else:
        clue_variants_loaded = False
        print("LOG: No clue_variants in cache")
else:
    cache_loaded = False
    clue_variants_loaded = False
    print("LOG: No cache found, will load on first request")
print("LOG: Initial cache load complete")

# Function to delete the cache file
def delete_cache():
    cache_file = base("car_cache.pkl")
    if os.path.exists(cache_file):
        os.remove(cache_file)
        print(f"Cache file deleted at {datetime.now(EST)}")




# Ensure the cache on-demand: if the cached day doesn't match current day, remove and regenerate
def ensure_car_cache_current():
    print("LOG: ensure_car_cache_current() started")
    global cached, cache_loaded, car, img, greyscale, width, height, clue, clue_variants, day_number, clue_variants_loaded
    cache_file = base("car_cache.pkl")
    print(f"LOG: Cache file path: {cache_file}")
    # If cache exists but for a different day, delete it
    if os.path.exists(cache_file):
        print("LOG: Cache file exists, checking if current")
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            print(f"LOG: Loaded cached data, day_number: {cached_data.get('day_number')}")
            current_day = get_current_day_number()
            print(f"LOG: Current day: {current_day}")
            if cached_data.get('day_number') != current_day:
                print("LOG: Cache is stale, deleting")
                try:
                    os.remove(cache_file)
                    print(f"Stale cache removed at {datetime.now(EST)}")
                except Exception as e0:
                    print(f"LOG: Error deleting stale cache: {e0}")
                    pass
                cached = None
                cache_loaded = False
                clue_variants_loaded = False
            else:
                print("LOG: Cache is current, loading into globals")
                # Load into globals if not already
                cached = cached_data
                cache_loaded = True
                car_data = cached_data['car']
                if isinstance(car_data, tuple):
                    print("LOG: Car data is tuple, unpacking")
                    car, img_data = car_data
                    img = Image.open(BytesIO(img_data))
                else:
                    print("LOG: Car data is dict, loading image")
                    car = car_data
                    img = Image.open(BytesIO(cached_data['img_data']))
                if 'clue_variants' in cached_data:
                    print("LOG: Loading clue_variants from cache")
                    clue_variants = cached_data['clue_variants']
                    clue_variants_loaded = True
                else:
                    print("LOG: No clue_variants in cache")
                    clue_variants_loaded = False
        except Exception as e1:
            print(f"LOG: Error loading cache: {e1}")
            # Corrupt cache - delete it
            try:
                os.remove(cache_file)
            except Exception as e2:
                print(f"LOG: Error deleting corrupt cache: {e2}")
                pass
            cached = None
            cache_loaded = False
            clue_variants_loaded = False

    # If no current cache, pick a car and save
    if not cache_loaded:
        print("LOG: No current cache, picking a car")
        car = chooseCar()
        if car is not None:
            print(f"LOG: Chose car: {car.get('Make')} {car.get('Model')}")
            print("LOG: Fetching image")
            response = requests.get(car["url"])
            img_data = response.content
            print("LOG: Image fetched, opening")
            img = Image.open(BytesIO(img_data))
            # Resize to max 800x600 to speed up processing
            max_size = (800, 600)
            print("LOG: Resizing image")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            # Re-encode to bytes after resize
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_data = img_byte_arr.getvalue()
            img = Image.open(BytesIO(img_data))
            cache_loaded = True
            try:
                print("LOG: Computing greyscale")
                # Compute clue_variants first
                greyscale = img.convert("L")
                width, height = greyscale.size
                day_number = get_current_day_number()
                print("LOG: Setting random seed")
                random.seed(day_number + SEED)
                print("LOG: Cropping clue")
                clue = greyscale.crop((random.randint(0, int(width*0.4)), random.randint(0, int(height*0.4)), int(width*0.6), int(height*0.6)))
                print("LOG: Creating clue variants")
                clue_variants = create_clue_variants(img, clue, maxGuesses)
                clue_variants_loaded = True
                print("LOG: Saving cache")
                save_car_cache(car, img_data, clue_variants)
            except Exception as e:
                print(f"LOG: Error computing/saving: {e}")
                pass
        else:
            print("LOG: No car found")

    # If cache loaded but clue_variants not, compute them
    if cache_loaded and not clue_variants_loaded:
        print("LOG: Cache loaded but no clue_variants, computing")
        greyscale = img.convert("L")
        width, height = greyscale.size
        day_number = get_current_day_number()
        random.seed(day_number + SEED)
        clue = greyscale.crop((random.randint(0, int(width*0.4)), random.randint(0, int(height*0.4)), int(width*0.6), int(height*0.6)))
        clue_variants = create_clue_variants(img, clue, maxGuesses)
        clue_variants_loaded = True
        # Resave cache with clue_variants
        try:
            img_data = cached['img_data'] if cached else None
            if img_data:
                print("LOG: Resaving cache with clue_variants")
                save_car_cache(car, img_data, clue_variants)
        except Exception as e:
            print(f"LOG: Error resaving cache: {e}")
            pass
    print("LOG: ensure_car_cache_current() completed")


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
    print("LOG: Received GET / request")
    # Ensure cache is current for this request (deletes stale cache)
    print("LOG: Calling ensure_car_cache_current()")
    ensure_car_cache_current()
    print("LOG: ensure_car_cache_current() completed")
    print("LOG: Opening index.html")
    with open(base("index.html"), "r", encoding="utf-8") as f:
        content = f.read()
    print("LOG: Read index.html content")
    print("LOG: Returning HTML response")
    return content

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

@app.get("/history-day/{day_number}")
async def get_history_day(day_number: int):
    """Get the car for a specific historical day"""
    print(f"LOG: Loading historical day {day_number}")
    
    # Use the same logic as chooseCar but for a specific day
    random.seed(day_number + SEED)
    shuffled = selectable_documents.copy()
    random.shuffle(shuffled)
    
    for car in shuffled:
        year = car.get("Year", "")
        name = f'"{car["Make"]} {car["Model"]}" {year}'
        from ddgs import DDGS
        try:
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
                        # Return car info without modifying global state
                        return {
                            "day_number": day_number,
                            "car_name": f"{car['Make']} {car['Model']}",
                            "make": car["Make"],
                            "model": car["Model"]
                        }
        except:
            continue
    
    return {"error": "No car found for this day"}

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

def get_car_for_day(day_number: int):
    """Get the correct car for a specific day number"""
    random.seed(day_number + SEED)
    shuffled = selectable_documents.copy()
    random.shuffle(shuffled)
    
    # Return the first car (matching the logic in chooseCar)
    return shuffled[0] if shuffled else None

@app.post("/check-guess")
async def check_guess(guess: dict):
    guessed_car_name = guess.get("car_name", "").strip()
    history_day = guess.get("day_number", None)  # Optional historical day parameter
    
    # Find the guessed car in documents
    guessed_car = None
    for doc in documents:
        full_name = f"{doc['Make']} {doc['Model']}"
        if full_name.lower() == guessed_car_name.lower():
            guessed_car = doc
            break
    
    if not guessed_car:
        return {"error": "Car not found"}
    
    # Get the correct car (either current day or historical)
    if history_day is not None:
        correct_car = get_car_for_day(history_day)
        if not correct_car:
            return {"error": "Could not determine correct car for that day"}
    else:
        correct_car = car
    
    # Compare with correct car and return comparison results
    correct_name = f"{correct_car['Make']} {correct_car['Model']}"
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
        "make_correct": guessed_car["Make"].lower() == correct_car["Make"].lower(),
        "comparisons": {
            "year": compare_value(safe_value(guessed_car["Year"]), safe_value(correct_car["Year"]), "number"),
            "cylinders": compare_value(safe_value(guessed_car["Cylinders"]), safe_value(correct_car["Cylinders"]), "cylinders"),
            "horsepower": compare_value(safe_value(guessed_car["Horsepower"]), safe_value(correct_car["Horsepower"]), "number"),
            "fuel_capacity_gal": compare_value(safe_value(guessed_car["Fuel capacity (gal)"]), safe_value(correct_car["Fuel capacity (gal)"]), "number"),
            "fuel_capacity_liters": compare_value(safe_value(guessed_car["Fuel capacity (L)"]), safe_value(correct_car["Fuel capacity (L)"]), "number"),
            "country": compare_value(safe_value(guessed_car["Country"]), safe_value(correct_car["Country"]), "string")
        },
        "correct_name": correct_name if is_correct else None  # Only reveal name if guess is correct
    }

@app.post("/reveal-hint")
async def reveal_hint(request: dict):
    """Reveal a specific column value as a hint"""
    column_name = request.get("column_name", "").strip().lower()
    history_day = request.get("day_number", None)
    
    # Get the correct car
    if history_day is not None:
        correct_car = get_car_for_day(history_day)
        if not correct_car:
            return {"error": "Could not determine correct car for that day"}
    else:
        correct_car = car
    
    column_map = {
        "year": safe_value(correct_car["Year"]),
        "cylinders": safe_value(correct_car["Cylinders"]),
        "hp": safe_value(correct_car["Horsepower"]),
        "fuel": f"{safe_value(correct_car['Fuel capacity (gal)'])} / {safe_value(correct_car['Fuel capacity (L)'])}",
        "country": safe_value(correct_car["Country"])
    }
    
    if column_name not in column_map:
        return {"error": "Invalid column name"}
    
    return {
        "column": column_name,
        "value": column_map[column_name]
    }

@app.post("/reveal-answer")
async def reveal_answer(request: dict = None):
    """Reveal the correct car name (for game over)"""
    history_day = request.get("day_number", None) if request else None
    
    # Get the correct car
    if history_day is not None:
        correct_car = get_car_for_day(history_day)
        if not correct_car:
            return {"error": "Could not determine correct car for that day"}
    else:
        correct_car = car
    
    return {
        "name": f"{correct_car['Make']} {correct_car['Model']}"
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

@app.get("/history-clue.png")
async def get_history_clue(day: int, guess: int = 0):
    """Get clue image for a specific historical day and guess number"""
    print(f"LOG: Loading history clue for day {day}, guess {guess}")
    
    # Get the car for this historical day
    random.seed(day + SEED)
    shuffled = selectable_documents.copy()
    random.shuffle(shuffled)
    
    historical_car = None
    historical_img = None
    
    for car in shuffled:
        year = car.get("Year", "")
        name = f'"{car["Make"]} {car["Model"]}" {year}'
        from ddgs import DDGS
        try:
            with DDGS() as ddgs:
                results = ddgs.images(name, max_results=1)
                for result in results:
                    r = result["image"]
                    try:
                        img_response = requests.get(r)
                        historical_img = Image.open(BytesIO(img_response.content))
                        # Resize to max 800x600 to match current day logic
                        max_size = (800, 600)
                        historical_img.thumbnail(max_size, Image.Resampling.LANCZOS)
                        historical_car = car
                        break
                    except:
                        continue
                if historical_car:
                    break
        except:
            continue
    
    if not historical_img:
        # Return a blank/error image if no car found
        blank_img = Image.new('RGB', (400, 300), color='gray')
        img_byte_arr = BytesIO()
        blank_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return StreamingResponse(img_byte_arr, media_type="image/png")
    
    # Create clue variants for this historical image
    greyscale_hist = historical_img.convert("L")
    width_hist, height_hist = greyscale_hist.size
    random.seed(day + SEED)
    clue_hist = greyscale_hist.crop((
        random.randint(0, int(width_hist*0.4)),
        random.randint(0, int(height_hist*0.4)),
        int(width_hist*0.6),
        int(height_hist*0.6)
    ))
    
    historical_clue_variants = create_clue_variants(historical_img, clue_hist, maxGuesses)
    
    # Clamp guess to valid range
    guess = max(0, min(guess, len(historical_clue_variants) - 1))
    
    img_byte_arr = BytesIO()
    historical_clue_variants[guess].save(img_byte_arr, format='PNG')
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