"""
Скрипт для добавления поля prefix и обновления пользователя FLOWXZ
"""

from app import app, db, User
import sqlite3

def add_prefix_column():
    """Добавляет колонку prefix если её нет"""
    try:
        with app.app_context():
            # Проверяем есть ли колонка
            conn = sqlite3.connect('instance/database.db')
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user)")
            columns = [col[1] for col in cursor.fetchall()]
            conn.close()
            
            if 'prefix' not in columns:
                print("➕ Добавляю колонку 'prefix' в таблицу User...")
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE user ADD COLUMN prefix VARCHAR(50)"))
                    conn.commit()
                print("✅ Колонка 'prefix' добавлена!")
            else:
                print("ℹ️  Колонка 'prefix' уже существует")
    except Exception as e:
        print(f"❌ Ошибка при добавлении колонки: {e}")

def update_flowxz_prefix():
    """Обновляет префикс пользователя FLOWXZ на Developer"""
    with app.app_context():
        user = User.query.filter_by(username='FLOWXZ').first()
        
        if not user:
            print("❌ Пользователь 'FLOWXZ' не найден!")
            return
        
        old_prefix = user.prefix if hasattr(user, 'prefix') else None
        user.prefix = 'Developer'
        
        db.session.commit()
        
        print(f"✅ Префикс пользователя 'FLOWXZ' обновлен!")
        print(f"   Старый префикс: {old_prefix if old_prefix else 'не был установлен'}")
        print(f"   Новый префикс: Developer")
        print(f"   ID пользователя: {user.id}")

if __name__ == '__main__':
    print("🔧 Обновление базы данных...\n")
    add_prefix_column()
    print()
    update_flowxz_prefix()
