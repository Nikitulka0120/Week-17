FROM python:3.11-slim

WORKDIR /app

COPY log-svc/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ ./proto/

RUN python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/logs.proto

COPY log-svc/main.py .

EXPOSE 50051

CMD ["python", "main.py"]
