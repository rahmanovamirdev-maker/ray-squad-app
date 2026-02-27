from app import app, db, User, ModelOperatorApplication

with app.app_context():
    # Проверяем все пользователей с командой 404
    users_404 = User.query.filter_by(team='404').all()
    print("=== Пользователи команды 404 ===")
    for user in users_404:
        print(f"ID: {user.id}, Username: {user.username}, Team: {user.team}")
        
    print("\n=== Анкеты операторов команды 404 ===")
    models_404 = ModelOperatorApplication.query.filter_by(team='404').all()
    for model in models_404:
        print(f"ID: {model.id}, Name: {model.full_name}, Owner: {model.owner_username}, Team: {model.team}")

    print("\n=== Все анкеты без команды (team=None) ===")
    models_none = ModelOperatorApplication.query.filter_by(team=None).all()
    for model in models_none:
        print(f"ID: {model.id}, Name: {model.full_name}, Owner: {model.owner_username}, Team: {model.team}")

    print("\n=== Анкеты от пользователей команды 404 (по owner_username) ===")
    for user in users_404:
        models = ModelOperatorApplication.query.filter_by(owner_username=user.username).all()
        for model in models:
            print(f"ID: {model.id}, Name: {model.full_name}, Owner: {model.owner_username}, Team: {model.team}")
