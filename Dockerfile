FROM python:3.14-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy requirements
COPY requirements.txt .

# Install dependencies with uv (faster than pip)
RUN uv pip install --system -r requirements.txt

# Copy app files
COPY . .

# Run the app
CMD ["python3", "main.py"]
