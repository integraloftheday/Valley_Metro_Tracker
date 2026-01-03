# Use a slim Python image to keep the container light
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies if required (geopy/pandas sometimes need them)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
# Note: Based on your freeze.txt, we install the listed dependencies
COPY freeze.txt .
RUN pip install --no-cache-dir -r freeze.txt

# Copy the rest of the application code
COPY . .

# Run the application
CMD ["python", "main.py"]
