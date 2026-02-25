"""
Скрипт для добавления таблицы ApplicantStatusSync в БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, ApplicantStatusSync

def create_sync_table():
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            insp = inspect(db.engine)
            
            # Проверяем существует ли таблица
            if 'applicant_status_sync' not in insp.get_table_names():
                print("✅ Создаю таблицу applicant_status_sync...")
                db.create_all()
                print("✅ Таблица успешно создана!")
            else:
                print("ℹ️ Таблица applicant_status_sync уже существует")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False
    
    return True

if __name__ == '__main__':
    print("Миграция для добавления таблицы синхронизации статусов")
    print("=" * 60)
    if create_sync_table():
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция не удалась!")
