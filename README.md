# ProductStats - Week-17 Final Project

Дашборд статистики товаров с микросервисной архитектурой (REST + gRPC + PostgreSQL).

## Что это?

Приложение отображает статистику товаров (просмотры и лайки). При запуске база данных PostgreSQL автоматически заполняется начальными товарами. Фронтенд показывает 2 интерактивных графика и общую таблицу всех товаров.

## Архитектура

Система состоит из следующих компонентов:
1. **Frontend (Nginx :3000)** - раздает статические файлы (HTML, CSS, JS) и проксирует запросы `/api/*` на бэкенд.
2. **Backend (FastAPI :8000)** - обслуживает REST API для управления товарами и получения статистики. Сохраняет данные в PostgreSQL. При каждом действии отправляет лог-запись в Log Service по протоколу gRPC.
3. **Log Service (gRPC :50051)** - микросервис логирования. Принимает логи по gRPC и хранит их в оперативной памяти (in-memory).
4. **PostgreSQL (:5432)** - реляционная база данных для хранения информации о товарах.

```
[Browser]  →  [Nginx :3000]  →  /api/*  →  [FastAPI :8000]  →  [PostgreSQL :5432]
                                               │
                                          gRPC (логи)
                                               ▼
                                      [Log Service :50051]
```

## Как запустить?

```bash
docker compose up --build
```

- **Фронтенд**: http://localhost:3000  
- **API docs**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/health  
- **Логи приложения**: http://localhost:8000/api/logs  

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Backend   | Python + FastAPI + Uvicorn |
| ORM / БД  | SQLAlchemy + PostgreSQL |
| Log Service | Python + gRPC (grpcio / grpcio-tools) |
| Frontend  | HTML + Vanilla CSS + Chart.js |
| Прокси    | Nginx |
| Оркестрация | Docker Compose |

## API эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/products` | Список всех товаров |
| GET | `/api/products/{id}` | Товар по ID |
| POST | `/api/products` | Создать товар |
| POST | `/api/products/{id}/like` | Поставить лайк товару |
| GET | `/api/stats` | Сводная статистика + топ-7 |
| GET | `/api/logs` | Проксировать логи из log-svc по gRPC |
| GET | `/health` | Healthcheck |
