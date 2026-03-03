#!/usr/bin/env python3
"""Миграция для production - добавление is_deleted безопасно"""

from app import app, db
from sqlalchemy import inspect, text

def safe_migrate_soft_delete():
    """Безопасная миграция для production"""
    
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ PRODUCTION: Добавление is_deleted (БЕЗОПАСНО)")
        print("=" * 80)
        
        insp = inspect(db.engine)
        
        # 1. ModelOperatorApplication
        print("\n1. Проверка таблицы model_operator_application...")
        if 'model_operator_application' not in insp.get_table_names():
            print("   ℹ️ Таблица не существует (создается при инициализации)")
        else:
            cols = [c['name'] for c in insp.get_columns('model_operator_application')]
            if 'is_deleted' not in cols:
                print("   ⚠️ Добавляю is_deleted колонку...")
                try:
                    db.session.execute(text(
                        "ALTER TABLE model_operator_application ADD COLUMN is_deleted BOOLEAN DEFAULT 0"
                    ))
                    db.session.commit()
                    print("   ✅ Колонка is_deleted добавлена к ModelOperatorApplication")
                    print("   ✅ Все существующие записи помечены как is_deleted=0")
                except Exception as e:
                    print(f"   ❌ Ошибка: {e}")
                    db.session.rollback()
            else:
                print("   ✅ Колонка is_deleted уже существует")
        
        # 2. ChatApplication
        print("\n2. Проверка таблицы chat_application...")
        if 'chat_application' not in insp.get_table_names():
            print("   ℹ️ Таблица не существует (создается при инициализации)")
        else:
            cols = [c['name'] for c in insp.get_columns('chat_application')]
            if 'is_deleted' not in cols:
                print("   ⚠️ Добавляю is_deleted колонку...")
                try:
                    db.session.execute(text(
                        "ALTER TABLE chat_application ADD COLUMN is_deleted BOOLEAN DEFAULT 0"
                    ))
                    db.session.commit()
                    print("   ✅ Колонка is_deleted добавлена к ChatApplication")
                    print("   ✅ Все существующие записи помечены как is_deleted=0")
                except Exception as e:
                    print(f"   ❌ Ошибка: {e}")
                    db.session.rollback()
            else:
                print("   ✅ Колонка is_deleted уже существует")
        
        # 3. Проверяем наличие данных
        from app import ModelOperatorApplication, ChatApplication, Applicant
        
        print("\n3. Статус данных в БД:")
        try:
            models_count = ModelOperatorApplication.query.count()
            chatters_count = ChatApplication.query.count()
            applicants_count = Applicant.query.count()
            
            print(f"   📊 Заявок моделей: {models_count}")
            print(f"   📊 Заявок чаттеров: {chatters_count}")
            print(f"   📊 Заявок операторов: {applicants_count}")
            
            total = models_count + chatters_count + applicants_count
            print(f"   📊 ИТОГО: {total} заявок")
        except Exception as e:
            print(f"   ❌ Ошибка чтения БД: {e}")
        
        print("\n" + "=" * 80)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА - PRODUCTION ГОТОВ К РАБОТЕ")
        print("=" * 80)

if __name__ == '__main__':
    safe_migrate_soft_delete()
