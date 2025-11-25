FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (add ffmpeg if pydub needs it)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend backend
COPY frontend frontend

RUN pip install --upgrade pip && pip install .  # installs project deps

EXPOSE 8000 8501

# Default to API (override for Streamlit)
CMD ["uvicorn", "backend.api_server:app", "--host", "0.0.0.0", "--port", "8000"]