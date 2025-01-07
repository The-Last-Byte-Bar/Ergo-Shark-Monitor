FROM python:3.12-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory and set permissions
RUN mkdir -p /app/logs && \
    chown -R 1000:1000 /app/logs

# Copy application code
COPY . .

# Set the user to run the application
USER 1000:1000

CMD ["python", "main.py"]