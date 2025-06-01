FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment variables
ENV FLASK_APP=app.main
ENV PORT=8000
EXPOSE $PORT

# Run Gunicorn with correct module path
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app.main:app"]
