from app import app, db, User

with app.app_context():
    user = User.query.filter_by(username='FLOWXZ').first()
    
    if user:
        print(f"Найден пользователь: {user.username}")
        print(f"Текущий префикс: {user.prefix if hasattr(user, 'prefix') else 'не установлен'}")
        
        user.prefix = 'Developer'
        db.session.commit()
        
        print(f"Новый префикс: {user.prefix}")
        print("✅ Префикс успешно обновлён!")
    else:
        print("❌ Пользователь FLOWXZ не найден")
