"""
Скрипт миграции базы данных через Flask ORM
"""
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from sqlalchemy import inspect, text

def migrate():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Проверяем существующие столбцы в таблице user
        user_columns = [col['name'] for col in inspector.get_columns('user')]
        
        print("Текущие столбцы в таблице user:", user_columns)
        
        # Добавляем crypto_wallet если его нет
        if 'crypto_wallet' not in user_columns:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN crypto_wallet VARCHAR(200)"))
                conn.commit()
            print("✅ Добавлен столбец crypto_wallet")
        else:
            print("ℹ️ Столбец crypto_wallet уже существует")
            
        # Добавляем earned_amount если его нет
        if 'earned_amount' not in user_columns:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN earned_amount FLOAT DEFAULT 0.0"))
                conn.commit()
            print("✅ Добавлен столбец earned_amount")
        else:
            print("ℹ️ Столбец earned_amount уже существует")
        
        # Проверяем существующие столбцы в таблице applicant
        applicant_columns = [col['name'] for col in inspector.get_columns('applicant')]
        
        print("\nТекущие столбцы в таблице applicant:", applicant_columns)
        
        # Добавляем status если его нет
        if 'status' not in applicant_columns:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE applicant ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"))
                conn.commit()
            print("✅ Добавлен столбец status")
        else:
            print("ℹ️ Столбец status уже существует")
        
        print("\n✅ Миграция завершена!")

if __name__ == '__main__':
    migrate()
