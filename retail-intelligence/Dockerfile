FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY retail ./retail
RUN pip install --no-cache-dir .
COPY web ./web
COPY artifacts ./artifacts
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "retail.api:app", "--host", "0.0.0.0", "--port", "8000"]
