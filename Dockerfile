# Eclair Subnet Validator
FROM python:3.12-slim

RUN apt-get update && apt-get install -y git curl ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY eclair.py ./
RUN uv pip install --system --no-cache -e .

CMD ["eclair"]
