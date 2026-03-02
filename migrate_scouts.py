#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Миграция для добавления новых полей к ScoutJoinApplication
"""

from app import app, db, ScoutJoinApplication
from sqlalchemy import text

with app.app_context():
    try:
        print("🔄 Проверяю таблицу ScoutJoinApplication...")
        
        # Проверяем существование таблицы
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('scout_join_application')]
        print(f"✓ Текущие колонки: {columns}")
        
        # Добавляем недостающие колонки
        with db.engine.connect() as connection:
            if 'status' not in columns:
                print("→ Добавляю колонку 'status'...")
                connection.execute(text("ALTER TABLE scout_join_application ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"))
                connection.commit()
                print("✓ Колонка 'status' добавлена")
            
            if 'approved_by' not in columns:
                print("→ Добавляю колонку 'approved_by'...")
                connection.execute(text("ALTER TABLE scout_join_application ADD COLUMN approved_by VARCHAR(120)"))
                connection.commit()
                print("✓ Колонка 'approved_by' добавлена")
            
            if 'rejected_by' not in columns:
                print("→ Добавляю колонку 'rejected_by'...")
                connection.execute(text("ALTER TABLE scout_join_application ADD COLUMN rejected_by VARCHAR(120)"))
                connection.commit()
                print("✓ Колонка 'rejected_by' добавлена")
            
            if 'reviewed_at' not in columns:
                print("→ Добавляю колонку 'reviewed_at'...")
                connection.execute(text("ALTER TABLE scout_join_application ADD COLUMN reviewed_at DATETIME"))
                connection.commit()
                print("✓ Колонка 'reviewed_at' добавлена")
        
        print("\n✓ Миграция успешно завершена!")
        
        # Показываем количество записей
        count = ScoutJoinApplication.query.count()
        print(f"📊 Всего заявок в БД: {count}")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
