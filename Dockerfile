# Use a lightweight Python base
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies for psycopg2 (Postgres)
RUN apt-get update && apt-get install -y gcc libpq-dev

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Run with Gunicorn on port 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

