FROM python:3.11-slim

# Install system dependencies required for Pillow and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python scripts
COPY *.py ./

# Create directories for shared data
RUN mkdir -p /app/shared/uploads /app/shared/outputs /app/.image_cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672

# Run the consumer
CMD ["python", "main.py"]
