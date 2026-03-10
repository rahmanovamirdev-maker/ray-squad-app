#!/usr/bin/env python3
"""
Миграция: добавление поля is_deleted в таблицу scout_join_application
"""

from app import app, db
from sqlalchemy import inspect, text

with app.app_context():
    print("=" * 80)
    print("МИГРАЦИЯ: Добавление is_deleted и team в scout_join_application")
    print("=" * 80)
    
    try:
        insp = inspect(db.engine)
        if 'scout_join_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('scout_join_application')]
            
            # Добавляем team
            if 'team' not in cols:
                print("✅ Добавляю столбец team...")
                db.session.execute(text(
                    "ALTER TABLE scout_join_application ADD COLUMN team VARCHAR(50)"
                ))
                db.session.commit()
                print("✅ Столбец team успешно добавлен!")
            else:
                print("ℹ️  Столбец team уже существует")
            
            # Добавляем is_deleted
            if 'is_deleted' not in cols:
                print("✅ Добавляю столбец is_deleted...")
                db.session.execute(text(
                    "ALTER TABLE scout_join_application ADD COLUMN is_deleted BOOLEAN DEFAULT 0"
                ))
                db.session.commit()
                print("✅ Столбец is_deleted успешно добавлен!")
            else:
                print("ℹ️  Столбец is_deleted уже существует")
        else:
            print("❌ Таблица scout_join_application не найдена!")
            
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        db.session.rollback()
    
    print("=" * 80)
    print("Миграция завершена!")
    print("=" * 80)
