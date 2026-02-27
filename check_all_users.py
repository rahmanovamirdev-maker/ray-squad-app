from app import app, db, User

with app.app_context():
    print("=== ВСЕ ПОЛЬЗОВАТЕЛИ ===")
    all_users = User.query.all()
    for user in all_users:
        print(f"ID: {user.id}, Username: {user.username}, Team: {user.team}")
