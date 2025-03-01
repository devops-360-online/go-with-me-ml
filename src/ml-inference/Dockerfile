FROM python:3.9-slim

WORKDIR /app

# Copy requirement file
COPY src/ml-inference/requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY src/ml-inference/app.py /app/

EXPOSE 8080

# Start the FastAPI server with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
