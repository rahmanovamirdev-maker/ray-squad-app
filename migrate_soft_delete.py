"""
Скрипт миграции для добавления мягкого удаления (soft delete).
Добавляет поле 'is_deleted' в таблицу applicant.
"""

from app import app, db
from sqlalchemy import inspect, text

def migrate_soft_delete():
    """Выполнить миграцию для добавления поля is_deleted"""
    with app.app_context():
        print("=" * 60)
        print("МИГРАЦИЯ: Добавление мягкого удаления для анкет")
        print("=" * 60)
        
        insp = inspect(db.engine)
        
        # Миграция таблицы applicant
        if 'applicant' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('applicant')]
            if 'is_deleted' not in cols:
                print("[✓] Добавляю столбец is_deleted в таблицу applicant...")
                # Добавляем столбец с значением по умолчанию False (0 для SQLite)
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("[✓] Столбец is_deleted добавлен в таблицу applicant")
                
                # Устанавливаем значение False для всех существующих записей
                print("[✓] Устанавливаю значение False для всех существующих записей...")
                db.session.execute(text("UPDATE applicant SET is_deleted = 0 WHERE is_deleted IS NULL"))
                db.session.commit()
                print("[✓] Все существующие записи обновлены")
            else:
                print("[!] Столбец is_deleted уже существует в таблице applicant")
        else:
            print("[!] Таблица applicant не найдена")
        
        print("=" * 60)
        print("МИГРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 60)
        print()
        print("Теперь при удалении анкет они будут помечаться как удаленные,")
        print("но останутся в базе данных и будут видны в админке.")
        print()

if __name__ == '__main__':
    migrate_soft_delete()
