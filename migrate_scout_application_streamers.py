"""
Миграция для добавления полей стримерш в ScoutJoinApplication
Добавляет поля: city, streaming_experience, motivation
"""
from app import app, db

def migrate():
    """Добавляет новые поля для анкеты стримерш"""
    with app.app_context():
        try:
            # Проверяем, нужна ли миграция
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('scout_join_application')]
            
            if 'city' in columns and 'streaming_experience' in columns and 'motivation' in columns:
                print("✅ Миграция уже выполнена. Все поля существуют.")
                return
            
            print("🔄 Начинаем миграцию...")
            
            # Добавляем новые поля
            with db.engine.connect() as conn:
                if 'city' not in columns:
                    conn.execute(db.text(
                        "ALTER TABLE scout_join_application ADD COLUMN city VARCHAR(100)"
                    ))
                    conn.commit()
                    print("✅ Добавлено поле 'city'")
                
                if 'streaming_experience' not in columns:
                    conn.execute(db.text(
                        "ALTER TABLE scout_join_application ADD COLUMN streaming_experience VARCHAR(50)"
                    ))
                    conn.commit()
                    print("✅ Добавлено поле 'streaming_experience'")
                
                if 'motivation' not in columns:
                    conn.execute(db.text(
                        "ALTER TABLE scout_join_application ADD COLUMN motivation TEXT"
                    ))
                    conn.commit()
                    print("✅ Добавлено поле 'motivation'")
                
                # Делаем старое поле persuasion_text nullable
                if 'persuasion_text' in columns:
                    try:
                        conn.execute(db.text(
                            "ALTER TABLE scout_join_application ALTER COLUMN persuasion_text DROP NOT NULL"
                        ))
                        conn.commit()
                        print("✅ Поле 'persuasion_text' теперь nullable")
                    except Exception as e:
                        print(f"⚠️  Не удалось изменить persuasion_text: {e}")
            
            print("✅ Миграция успешно завершена!")
            
        except Exception as e:
            print(f"❌ Ошибка при миграции: {e}")
            raise

if __name__ == '__main__':
    migrate()
