"""
Скрипт миграции для добавления поддержки команд/сквадов.
Добавляет поле 'team' в таблицы user, applicant и model_operator_application.
"""

from app import app, db
from sqlalchemy import inspect, text

def migrate_teams():
    """Выполнить миграцию для добавления поля team"""
    with app.app_context():
        print("=" * 60)
        print("МИГРАЦИЯ: Добавление системы команд/сквадов")
        print("=" * 60)
        
        insp = inspect(db.engine)
        
        # Миграция таблицы user
        if 'user' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('user')]
            if 'team' not in cols:
                print("[✓] Добавляю столбец team в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN team VARCHAR(50)"))
                db.session.commit()
                print("[✓] Столбец team добавлен в таблицу user")
            else:
                print("[!] Столбец team уже существует в таблице user")
        
        # Миграция таблицы applicant
        if 'applicant' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('applicant')]
            if 'team' not in cols:
                print("[✓] Добавляю столбец team в таблицу applicant...")
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN team VARCHAR(50)"))
                db.session.commit()
                print("[✓] Столбец team добавлен в таблицу applicant")
            else:
                print("[!] Столбец team уже существует в таблице applicant")
        
        # Миграция таблицы model_operator_application
        if 'model_operator_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('model_operator_application')]
            if 'team' not in cols:
                print("[✓] Добавляю столбец team в таблицу model_operator_application...")
                db.session.execute(text("ALTER TABLE model_operator_application ADD COLUMN team VARCHAR(50)"))
                db.session.commit()
                print("[✓] Столбец team добавлен в таблицу model_operator_application")
            else:
                print("[!] Столбец team уже существует в таблице model_operator_application")
        
        print("=" * 60)
        print("МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 60)
        print("\nЭТИ КОМАНДЫ ДОСТУПНЫ:")
        print("1. Delta")
        print("2. Den")
        print("3. Amir")
        print("4. 404")
        print("5. Bobik")
        print("6. Oir")
        print("7. Gordon")
        print("8. Rey")
        print("\nТеперь доступны следующие возможности:")
        print("• Админы видят только анкеты своей команды")
        print("• Owner и Developer видят все анкеты")
        print("• Премиум фильтр по командам")
        print("• Выбор команды при создании пользователя")
        print("=" * 60)

if __name__ == '__main__':
    migrate_teams()
