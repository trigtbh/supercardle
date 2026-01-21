import os
import random
import csv
import re
from bs4 import BeautifulSoup

folder = 'car_specs'
columns = set()
car_data = {}
car_columns = {}

# Multi-word makes (lowercased for case-insensitive comparison)
multi_word_makes = {
    'alfa romeo',
    'aston martin',
    'baic motor',
    'dr motor',
    'ds automobiles',
    'gordon murray automotive',
    'land rover',
    'lucid motors',
    'maruti suzuki',
    'mercedes benz',
    'ram trucks',
    'rolls royce',
    'scout motors',
    'tata motors'
}

for filename in os.listdir(folder):
    if filename.endswith('.txt'):
        filepath = os.path.join(folder, filename)
        # Extract car name by removing the suffix
        car_name_full = filename.replace("Photos, engines & full specs.txt", "").strip()
        car_name = car_name_full
        year = None
        # Check for (XXXX-...) at the end and remove it
        if car_name_full.endswith(')'):
            start = car_name_full.rfind('(')
            if start != -1:
                inside = car_name_full[start+1:-1]
                parts = inside.split('-')
                if parts and len(parts[0]) == 4 and parts[0].isdigit():
                    year = parts[0]
                # Always remove the parentheses
                car_name = car_name_full[:start].strip()
        # If no year found, check if starts with 4-digit year
        if year is None and len(car_name_full) >= 4 and car_name_full[:4].isdigit():
            year = car_name_full[:4]
            car_name = car_name_full[5:].strip()
        
        # Remove any remaining parentheses from car_name
        car_name = car_name.replace('(', '').replace(')', '')
        
        # Separate make and model
        car_name_lower = car_name.lower()
        make = None
        model = None
        # Special case for MGU9
        if car_name_lower == 'mgu9':
            make = 'MG'
            model = 'U9'
        else:
            for mwm in multi_word_makes:
                if car_name_lower.startswith(mwm):
                    make = car_name[:len(mwm)].strip().title()
                    model = car_name[len(mwm):].strip()
                    break
            if not make:
                parts = car_name.split(' ', 1)
                make = parts[0].title()
                model = parts[1] if len(parts) > 1 else ''
        
        # Make specific makes all-caps
        if make.lower() in ['baic', 'bmw', 'ds', 'gmc', 'ram', 'seat']:
            make = make.upper()
        elif make.lower() == 'mclaren':
            make = 'McLaren'
        
        make = make.replace("Mercedes Benz", "Mercedes-Benz")
        make = make.replace("Rolls Royce", "Rolls-Royce")
        car_name = car_name.replace("Mercedes Benz", "Mercedes-Benz")

        # Normalize model: title-case any word that is not all-caps (keep acronyms like 'GT' as-is)
        if model:
            parts = model.split()
            norm_parts = []
            for p in parts:
                if p.isupper():
                    norm_parts.append(p)
                else:
                    norm_parts.append(p.title())
            model = ' '.join(norm_parts)

        car_data[car_name] = {'year': year, 'make': make, 'model': model, 'cylinders': '', 'power': '', 'torque': '', 'fuel_capacity': '', 'horsepower': ''}
        car_columns[car_name] = set()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table', class_='techdata')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    tds = row.find_all('td')
                    if len(tds) >= 2:
                        left_text = tds[0].get_text(strip=True).rstrip(':')
                        right_text = tds[1].get_text(strip=True)
                        car_columns[car_name].add(left_text)
                        columns.add(left_text)
                        if left_text == 'Cylinders':
                            car_data[car_name]['cylinders'] = right_text
                        elif left_text == 'Power':
                            car_data[car_name]['power'] = right_text
                        elif left_text == 'Torque':
                            car_data[car_name]['torque'] = right_text
                        elif left_text == 'Fuel capacity':
                            car_data[car_name]['fuel_capacity'] = right_text
                # Extract horsepower from the power string using regex (numbers before 'HP' or 'BHP')
                power_str = car_data[car_name].get('power', '')
                hp_found = None
                if power_str:
                    # try to find a number followed by HP (e.g., '272 HP')
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:HP|BHP)\b", power_str, flags=re.IGNORECASE)
                    if m:
                        # use integer part if possible
                        hp_found = m.group(1).split('.')[0]
                    else:
                        # fallback: look for tokens like 'RPM375' (digits after RPM)
                        for token in power_str.split():
                            t = token.strip()
                            if t.upper().startswith('RPM'):
                                digits = ''.join(ch for ch in t[3:] if ch.isdigit())
                                if digits:
                                    hp_found = digits
                                    break
                if hp_found:
                    car_data[car_name]['horsepower'] = hp_found
        except Exception as e:
            print(f"Error processing {filename}: {e}")

# Filter cars: must have year and required columns
required_columns = {'Cylinders', 'Power', 'Torque', 'Fuel capacity'}
filtered_car_data = {name: data for name, data in car_data.items()
                     if data['year'] and data.get('make') and data.get('model') and required_columns.issubset(car_columns.get(name, set()))}


for k, v in filtered_car_data.items():
    if "power" not in v: 
        print(k, v)
        input()
        continue
    # tokens = v["power"].split(" ")
    # for t in tokens:
    #     if t.startswith("RPM"):
    #         v["power"] = t[3:]
    #         break

    v["torque"] = v["torque"].split(" ")[0]
    v["fuel_capacity"] = v["fuel_capacity"].split(" ")[0]



# Export to CSV (include spec columns)
with open('car_data.csv', 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['Year', 'Make', 'Model', 'Car Name', 'Cylinders', 'Power', 'Torque', 'Fuel capacity', 'Horsepower']
    
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for name in sorted(filtered_car_data.keys()):
        data = filtered_car_data[name]
        writer.writerow({
            'Year': data['year'],
            'Make': data['make'],
            'Model': data['model'],
            'Car Name': name,
            'Cylinders': data.get('cylinders', ''),
            'Power': data.get('power', ''),
            'Torque': data.get('torque', ''),
            'Fuel capacity': data.get('fuel_capacity', ''),
            'Horsepower': data.get('horsepower', '')
        })

print("\nData exported to car_data.csv")