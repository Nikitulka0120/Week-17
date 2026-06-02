import os
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
import grpc
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database import Product as ProductModel, get_db
import logs_pb2
import logs_pb2_grpc

APP_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")
LOG_SVC_HOST = os.getenv("LOG_SVC_HOST", "log-svc:50051")

grpc_channel = grpc.insecure_channel(LOG_SVC_HOST)
logs_stub = logs_pb2_grpc.LogServiceStub(grpc_channel)

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_state_change = time.time()

    def allow_request(self):
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change > self.recovery_timeout:
                self.state = "HALF-OPEN"
                self.last_state_change = now
                print("[CIRCUIT BREAKER] Entering HALF-OPEN state, testing connection...")
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        if self.state != "CLOSED":
            print("[CIRCUIT BREAKER] Service recovered! Closing circuit.")
            self.state = "CLOSED"
            self.last_state_change = time.time()

    def record_failure(self):
        self.failure_count += 1
        print(f"[CIRCUIT BREAKER] Failure recorded ({self.failure_count}/{self.failure_threshold})")
        if self.failure_count >= self.failure_threshold and self.state != "OPEN":
            print(f"[CIRCUIT BREAKER] Threshold reached! Tripping circuit to OPEN for {self.recovery_timeout} seconds.")
            self.state = "OPEN"
            self.last_state_change = time.time()

log_cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

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
    views: Optional[int] = 0
    likes: Optional[int] = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None

class PopularityUpdate(BaseModel):
    views: Optional[int] = None
    likes: Optional[int] = None

def _send_log(action: str, details: str):
    if not log_cb.allow_request():
        print(f"[FALLBACK LOG] {action} | {details}")
        return

    max_retries = 3
    backoff = 0.5
    
    for attempt in range(max_retries):
        try:
            logs_stub.SendLog(
                logs_pb2.LogEntry(
                    service="backend",
                    action=action,
                    details=details,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ),
                timeout=1.5,
            )
            log_cb.record_success()
            return
        except Exception as exc:
            print(f"[WARN] Попытка {attempt+1}/{max_retries} логирования не удалась: {exc}")
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                log_cb.record_failure()
                print(f"[FALLBACK LOG] {action} | {details}")

app = FastAPI(title="backend", root_path=APP_ROOT_PATH)

CONNECTIONS: set[WebSocket] = set()

@app.websocket("/ws/{room_id}")
async def websocket_signaling(websocket: WebSocket, room_id: str):
    await websocket.accept()
    CONNECTIONS.add(websocket)
    try:
        async for message in websocket.iter_text():
            for conn in list(CONNECTIONS):
                if conn != websocket:
                    await conn.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        CONNECTIONS.discard(websocket)

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
    p = ProductModel(
        name=data.name,
        category=data.category,
        views=data.views if data.views is not None else 0,
        likes=data.likes if data.likes is not None else 0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    _send_log("create_product", f"Создан товар id={p.id} ({p.name}), views={p.views}, likes={p.likes}")
    return p

@app.patch("/api/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    old_name = p.name
    if data.name is not None:
        p.name = data.name
    db.commit()
    db.refresh(p)
    _send_log("update_product", f"Товар id={product_id} переименован: '{old_name}' -> '{p.name}'")
    return p

@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    name = p.name
    db.delete(p)
    db.commit()
    _send_log("delete_product", f"Удален товар id={product_id} ({name})")

@app.put("/api/products/{product_id}/popularity", response_model=ProductOut)
def set_popularity(product_id: int, data: PopularityUpdate, db: Session = Depends(get_db)):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if data.views is not None:
        p.views = data.views
    if data.likes is not None:
        p.likes = data.likes
    db.commit()
    db.refresh(p)
    _send_log("set_popularity", f"Обновлена популярность товара id={product_id} ({p.name}): views={p.views}, likes={p.likes}")
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
    if not log_cb.allow_request():
        raise HTTPException(
            status_code=503, 
            detail="Log-сервис временно недоступен (Circuit Breaker OPEN). Попробуйте позже."
        )
    try:
        resp = logs_stub.GetLogs(logs_pb2.GetLogsRequest(limit=limit), timeout=3)
        log_cb.record_success()
        return [
            {"service": e.service, "action": e.action, "details": e.details, "timestamp": e.timestamp}
            for e in resp.logs
        ]
    except Exception as exc:
        log_cb.record_failure()
        raise HTTPException(status_code=502, detail=f"Log-сервис недоступен: {exc}")
