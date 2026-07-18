# PBM backend(FastAPI)。docker compose up での実行検証は未実施(TASKS T-112, A-204)
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "pbm.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
