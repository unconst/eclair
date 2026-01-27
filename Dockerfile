# SigmaZero Subnet Validator
FROM python:3.12-slim

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv
COPY . .
RUN uv pip install --system --no-cache -e .

CMD ["python", "validator.py"]
