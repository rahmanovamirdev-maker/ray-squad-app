"""
Скрипт для создания аккаунта владельца
"""

from app import app, db, User
from werkzeug.security import generate_password_hash

def create_owner():
    with app.app_context():
        # Проверяем существует ли уже такой пользователь
        existing = User.query.filter_by(username='liamkizz').first()
        if existing:
            print(f"❌ Пользователь 'liamkizz' уже существует!")
            print(f"   ID: {existing.id}")
            print(f"   Владелец: {existing.is_owner}")
            print(f"   Админ: {existing.is_admin}")
            return
        
        # Создаем владельца
        owner = User(
            username='liamkizz',
            password_hash=generate_password_hash('liamkizz12332'),
            is_owner=True,
            is_admin=True,  # Владелец также админ
            is_guest=False,
            can_submit=True
        )
        
        db.session.add(owner)
        db.session.commit()
        
        print("✅ Аккаунт владельца создан!")
        print(f"   Логин: liamkizz")
        print(f"   Пароль: liamkizz12332")
        print(f"   ID: {owner.id}")
        print(f"\n🔐 Войти можно на: http://46.101.218.79/login")

if __name__ == '__main__':
    create_owner()
