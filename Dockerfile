# Use official Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app.py .
COPY model.py .
COPY mysql_database.py .
COPY static/ ./static/
COPY templates/ ./templates/

# Database environment variables
ENV MYSQL_HOST=db \
    MYSQL_PORT=3306 \
    MYSQL_USER=root \
    MYSQL_PASSWORD=gayathri \
    MYSQL_DATABASE=isrm

# Expose Flask port
EXPOSE 5000

# Run the Flask app
CMD ["python", "app.py"]
