from app import app, db, User, ModelOperatorApplication

TEAMS = ['Delta', 'Den', 'ХАЦКЕР', '404', 'Bobik', 'Oir', 'Gordon', 'Rey']

with app.app_context():
    print("=" * 80)
    print("ПРОВЕРКА АНКЕТ ПО КОМАНДАМ")
    print("=" * 80)
    
    for team in TEAMS:
        print(f"\n{'=' * 80}")
        print(f"КОМАНДА: {team}")
        print(f"{'=' * 80}")
        
        # Получаем всех пользователей этой команды
        users = User.query.filter_by(team=team).all()
        print(f"Пользователей в команде {team}: {len(users)}")
        
        if not users:
            print(f"⚠️  В команде {team} НЕТ пользователей!")
        else:
            for user in users:
                print(f"  - {user.username} (ID: {user.id})")
        
        # Получаем все анкеты этой команды
        models = ModelOperatorApplication.query.filter_by(team=team).all()
        print(f"\nАнкет с team={team}: {len(models)}")
        
        if models:
            for model in models:
                print(f"  - ID: {model.id}, Имя: {model.full_name}, Owner: {model.owner_username}")
        
        # Получаем анкеты от пользователей этой команды
        if users:
            usernames = [u.username for u in users]
            models_from_users = ModelOperatorApplication.query.filter(
                ModelOperatorApplication.owner_username.in_(usernames)
            ).all()
            
            print(f"\nАнкет от пользователей команды {team}: {len(models_from_users)}")
            for model in models_from_users:
                print(f"  - ID: {model.id}, Имя: {model.full_name}, Owner: {model.owner_username}, Team_в_БД: {model.team}")
            
            # ПРОБЛЕМА: если анкеты есть, но team=None
            problem_models = [m for m in models_from_users if m.team != team]
            if problem_models:
                print(f"\n❌ ПРОБЛЕМА: {len(problem_models)} анкет не подписаны на правильную команду!")
                for model in problem_models:
                    print(f"     ID: {model.id}, team в БД: {model.team}, должна быть: {team}")
            else:
                print(f"\n✅ Все анкеты правильно подписаны на команду {team}")
    
    # ИТОГО
    print(f"\n{'=' * 80}")
    print("ИТОГО")
    print(f"{'=' * 80}")
    all_models_none = ModelOperatorApplication.query.filter_by(team=None).all()
    print(f"Анкет БЕЗ КОМАНДЫ (team=None): {len(all_models_none)}")
    if all_models_none:
        for model in all_models_none:
            print(f"  - ID: {model.id}, Имя: {model.full_name}, Owner: {model.owner_username}")
