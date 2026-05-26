import os
import random
from sqlalchemy.orm import Session
from database import init_db, get_db, Product as ProductModel

NAMES = [
    "Смартфон Galaxy", "Ноутбук ProBook", "Наушники SoundPro",
    "Умные часы FitBand", "Планшет MediaPad", "Клавиатура MechType",
    "Мышь SilentClick", "Монитор ClearView", "Веб-камера CamHD",
    "Колонка BassBoost", "Зарядка QuickCharge", "USB-хаб MultiPort",
    "SSD накопитель", "Роутер NetFast", "Игровой контроллер",
]
CATEGORIES = ["Электроника", "Аксессуары", "Периферия", "Гаджеты"]

def seed_data(db: Session):
    if db.query(ProductModel).count() > 0:
        return
    for name in random.sample(NAMES, 10):
        db.add(ProductModel(
            name=name,
            category=random.choice(CATEGORIES),
            views=random.randint(100, 10000),
            likes=random.randint(0, 500),
        ))
    db.commit()

def main():
    print("Starting database initialization...")
    init_db()
    db = next(get_db())
    try:
        seed_data(db)
        print("Database initialized and seeded successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
