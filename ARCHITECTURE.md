# Архитектура проекта likes-s17

## Обзор
Проект: **likes-s17** - сервис статистики товаров и лайков.

Система состоит из следующих компонентов:
1. **Backend** (FastAPI, REST) - единый сервис, обслуживающий CRUD товаров, лайки, статистику. Хранит данные в PostgreSQL через SQLAlchemy.
2. **Log Service** (gRPC) - микросервис логирования. Принимает логи от Backend по gRPC при каждом действии (просмотр, лайк, создание товара). Отдаёт лог-записи по запросу.
3. **PostgreSQL** - реляционная БД для хранения товаров и их популярности. Используется обоими сервисами (backend напрямую, log-svc - через backend-прокси).
4. **Frontend** (nginx + HTML/JS) - статический фронтенд с графиками Chart.js. Проксирует `/api/` запросы на Backend.

## Диаграмма взаимодействия

```
[Браузер] --HTTP--> [Frontend (nginx:3000)]
                         |
                    proxy /api/
                         |
                         v
                  [Backend (FastAPI:8000)] --SQLAlchemy--> [PostgreSQL:5432]
                         |
                    gRPC (логи)
                         |
                         v
                  [Log Service (gRPC:50051)]
```

## Протоколы
- **REST** - Frontend <-> Backend (внешний API для фронтенда)
- **gRPC** - Backend -> Log Service (межсервисное общение, пакет `logs`, сервис `LogService`)

## Технологический стек
- **Язык**: Python
- **Фреймворк**: FastAPI + Uvicorn
- **ORM**: SQLAlchemy
- **База данных**: PostgreSQL
- **gRPC**: grpcio / grpcio-tools
- **Фронтенд**: HTML, JavaScript, Chart.js
- **Контейнеризация**: Docker + Docker Compose

## Решения
- Выбран **REST** для внешнего API, так как это удобно для фронтенда.
- Выбран **gRPC** для передачи логов между Backend и Log Service, так как важна скорость.
- Выбран **SQLAlchemy** в качестве ORM для удобной работы с PostgreSQL.
- Backend совмещает функции управления товарами и статистики - это упрощает архитектуру и уменьшает количество сетевых вызовов.

## Запуск
```bash
docker-compose up --build
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Логи: http://localhost:8000/api/logs

## CI/CD
Пайплайн описан в `.github/workflows/ci.yml`. Запускается при пуше или PR в `weeks/week-17/starter/`.

**Порядок работы:**
1. Поднимается PostgreSQL + Log Service, ожидается healthcheck БД.
2. Поднимается Backend, ожидается `/health`.
3. Запускаются проверки REST API:
   - `GET /api/products` - список не пуст
   - `GET /api/products/1` - товар найден
   - `POST /api/products` - создание нового товара
   - `POST /api/products/{id}/like` - инкремент лайков
   - `GET /api/products/999` - возвращает 404
   - `GET /api/stats` - статистика не пуста
4. Проверяется gRPC-логирование: `GET /api/logs` - записи присутствуют.
5. Поднимается Frontend, проверяется nginx-проксирование `/api/`.
6. Контейнеры останавливаются и удаляются.
