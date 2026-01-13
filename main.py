import pandas as pd
import os

basepath = os.path.dirname(os.path.realpath(__file__))
base = lambda p: os.path.join(basepath, p)

df = pd.read_csv(base("cars.csv"))
documents = df.to_dict("records")

