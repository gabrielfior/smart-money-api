FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Environment variables (set these in deployment platform)
ENV PORT=8000

# Run the application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}