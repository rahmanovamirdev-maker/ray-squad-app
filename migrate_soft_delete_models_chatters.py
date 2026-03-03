#!/usr/bin/env python3
"""Миграция для добавления is_deleted колонки к ModelOperatorApplication и ChatApplication"""

from app import app, db
from sqlalchemy import inspect, text

def migrate_soft_delete():
    """Добавить is_deleted колонку к таблицам если её нет"""
    
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ: Добавление мягкого удаления для моделей и чаттеров")
        print("=" * 80)
        
        insp = inspect(db.engine)
        
        # 1. ModelOperatorApplication
        print("\n1. Проверка таблицы ModelOperatorApplication...")
        if 'model_operator_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('model_operator_application')]
            if 'is_deleted' not in cols:
                print("   ⚠️ Колонка is_deleted не найдена, добавляю...")
                try:
                    db.session.execute(text("ALTER TABLE model_operator_application ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    print("   ✅ Колонка is_deleted успешно добавлена к ModelOperatorApplication")
                except Exception as e:
                    print(f"   ❌ Ошибка при добавлении колонки: {e}")
                    db.session.rollback()
            else:
                print("   ✅ Колонка is_deleted уже существует в ModelOperatorApplication")
        else:
            print("   ℹ️ Таблица model_operator_application не существует (создается при инициализации)")
        
        # 2. ChatApplication
        print("\n2. Проверка таблицы ChatApplication...")
        if 'chat_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('chat_application')]
            if 'is_deleted' not in cols:
                print("   ⚠️ Колонка is_deleted не найдена, добавляю...")
                try:
                    db.session.execute(text("ALTER TABLE chat_application ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    print("   ✅ Колонка is_deleted успешно добавлена к ChatApplication")
                except Exception as e:
                    print(f"   ❌ Ошибка при добавлении колонки: {e}")
                    db.session.rollback()
            else:
                print("   ✅ Колонка is_deleted уже существует в ChatApplication")
        else:
            print("   ℹ️ Таблица chat_application не существует (создается при инициализации)")
        
        print("\n" + "=" * 80)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 80)

if __name__ == '__main__':
    migrate_soft_delete()
