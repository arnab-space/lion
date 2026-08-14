# Use the official Playwright Python image (includes Chromium and OS dependencies)
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your scraper code into the container
COPY . .

# Expose the port Render uses
EXPOSE 10000

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
