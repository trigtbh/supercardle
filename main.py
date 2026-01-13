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