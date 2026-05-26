import os
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException, Depends
import grpc
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database import Product as ProductModel, get_db
import logs_pb2
import logs_pb2_grpc

APP_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")
LOG_SVC_HOST = os.getenv("LOG_SVC_HOST", "log-svc:50051")

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    views: int
    likes: int

class ProductCreate(BaseModel):
    name: str
    category: str

def _send_log(action: str, details: str):
    try:
        channel = grpc.insecure_channel(LOG_SVC_HOST)
        stub = logs_pb2_grpc.LogServiceStub(channel)
        stub.SendLog(
            logs_pb2.LogEntry(
                service="backend",
                action=action,
                details=details,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
            timeout=2,
        )
        channel.close()
    except Exception as exc:
        print(f"[WARN] Не удалось отправить лог: {exc}")

app = FastAPI(title="backend", root_path=APP_ROOT_PATH)
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/products", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    _send_log("list_products", f"Запрошен список товаров ({len(products)} шт.)")
    return products

@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    _send_log("get_product", f"Запрошен товар id={product_id} ({p.name})")
    return p

@app.post("/api/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    p = ProductModel(name=data.name, category=data.category, views=0, likes=0)
    db.add(p)
    db.commit()
    db.refresh(p)
    _send_log("create_product", f"Создан товар id={p.id} ({p.name})")
    return p

@app.post("/api/products/{product_id}/like", response_model=ProductOut)
def like_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    p.likes += 1
    db.commit()
    db.refresh(p)
    _send_log("like_product", f"Лайк товару id={product_id} ({p.name}), всего лайков: {p.likes}")
    return p

@app.delete("/api/products/{product_id}/like", response_model=ProductOut)
def unlike_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if p.likes > 0:
        p.likes -= 1
        db.commit()
        db.refresh(p)
        _send_log("unlike_product", f"Удален лайк товару id={product_id} ({p.name}), всего лайков: {p.likes}")
    return p

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    if not products:
        return {"total_products": 0, "total_views": 0, "total_likes": 0, "top_by_views": [], "top_by_likes": []}

    total_views = sum(p.views for p in products)
    total_likes = sum(p.likes for p in products)

    top_views = sorted(products, key=lambda p: p.views, reverse=True)[:7]
    top_likes = sorted(products, key=lambda p: p.likes, reverse=True)[:7]

    _send_log("get_stats", f"Запрошена статистика ({len(products)} товаров)")
    return {
        "total_products": len(products),
        "total_views": total_views,
        "total_likes": total_likes,
        "top_by_views": [{"id": p.id, "name": p.name, "value": p.views} for p in top_views],
        "top_by_likes": [{"id": p.id, "name": p.name, "value": p.likes} for p in top_likes],
    }

@app.get("/api/logs")
def get_logs(limit: int = 50):
    try:
        channel = grpc.insecure_channel(LOG_SVC_HOST)
        stub = logs_pb2_grpc.LogServiceStub(channel)
        resp = stub.GetLogs(logs_pb2.GetLogsRequest(limit=limit), timeout=5)
        channel.close()
        return [
            {"service": e.service, "action": e.action, "details": e.details, "timestamp": e.timestamp}
            for e in resp.logs
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Log-сервис недоступен: {exc}")
