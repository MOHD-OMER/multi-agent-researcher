FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user (for HuggingFace Spaces)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Default: run Gradio frontend
EXPOSE 7860
CMD ["python", "frontend/app.py"]
