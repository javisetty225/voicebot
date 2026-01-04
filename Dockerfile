FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml pyproject.toml
COPY README.md README.md
COPY src src

RUN pip install --upgrade pip && pip install .

EXPOSE 8000 8501

CMD ["uvicorn", "src.main:create_app", "--host", "0.0.0.0", "--port", "8000"]