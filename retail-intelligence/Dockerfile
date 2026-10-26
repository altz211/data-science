# Serves the dashboard and the API. Bring your own trained model with
#   docker run -p 8000:8000 -v "$PWD/data:/app/data" retail-intelligence
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md requirements.txt ./
COPY retail ./retail
RUN pip install --no-cache-dir -r requirements.txt .
COPY sql ./sql
COPY web ./web
EXPOSE 8000
CMD ["uvicorn", "retail.api:app", "--host", "0.0.0.0", "--port", "8000"]
