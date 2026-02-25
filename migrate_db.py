"""
Скрипт миграции базы данных для добавления новых полей
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    
    try:
        # Проверяем и добавляем crypto_wallet в таблицу user
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN crypto_wallet VARCHAR(200)")
            print("✅ Добавлен столбец crypto_wallet в таблицу user")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Столбец crypto_wallet уже существует")
            else:
                raise
        
        # Проверяем и добавляем earned_amount в таблицу user
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN earned_amount FLOAT DEFAULT 0.0")
            print("✅ Добавлен столбец earned_amount в таблицу user")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Столбец earned_amount уже существует")
            else:
                raise
        
        # Проверяем и добавляем status в таблицу applicant
        try:
            cursor.execute("ALTER TABLE applicant ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
            print("✅ Добавлен столбец status в таблицу applicant")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Столбец status уже существует")
            else:
                raise
        
        conn.commit()
        print("\n✅ Миграция успешно завершена!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
