"""
Миграция для изменения полей в таблице guest_answer
- Переименовываем guest_phone в guest_age
- Добавляем guest_adult_exp
- Добавляем guest_work_hours
"""

from app import app, db
from sqlalchemy import text

def migrate_guest_fields():
    with app.app_context():
        print("Начало миграции полей гостевых анкет...")
        
        try:
            # Проверяем существующие столбцы
            result = db.session.execute(text("PRAGMA table_info(guest_answer)"))
            columns = [row[1] for row in result.fetchall()]
            print(f"Текущие столбцы: {columns}")
            
            # Добавляем новые столбцы, если их нет
            if 'guest_age' not in columns:
                print("Добавляю столбец guest_age...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_age VARCHAR(10)"))
                db.session.commit()
                print("✓ Столбец guest_age добавлен")
            
            if 'guest_adult_exp' not in columns:
                print("Добавляю столбец guest_adult_exp...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_adult_exp VARCHAR(500)"))
                db.session.commit()
                print("✓ Столбец guest_adult_exp добавлен")
            
            if 'guest_work_hours' not in columns:
                print("Добавляю столбец guest_work_hours...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_work_hours VARCHAR(200)"))
                db.session.commit()
                print("✓ Столбец guest_work_hours добавлен")
            
            # Копируем данные из guest_phone в guest_age (если guest_phone существует)
            if 'guest_phone' in columns:
                print("Копирую данные из guest_phone в guest_age...")
                db.session.execute(text("UPDATE guest_answer SET guest_age = guest_phone WHERE guest_age IS NULL"))
                db.session.commit()
                print("✓ Данные скопированы")
                
                # В SQLite невозможно удалить столбец напрямую, но можно оставить его пустым
                print("⚠ Примечание: столбец guest_phone останется в таблице (SQLite не поддерживает DROP COLUMN)")
                print("  Он просто не будет использоваться в коде")
            
            print("\n✓ Миграция успешно завершена!")
            
        except Exception as e:
            print(f"✗ Ошибка при миграции: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_guest_fields()
