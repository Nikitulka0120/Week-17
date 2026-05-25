FROM python:3.11-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY proto/ ./proto/
RUN python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/logs.proto
COPY backend/ .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
