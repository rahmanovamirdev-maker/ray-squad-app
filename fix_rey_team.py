"""
Универсальный скрипт для исправления команды (team) всех анкет
Проверяет для каждого пользователя что у всех его анкет установлена его команда
"""

from app import app, db, User, Applicant, ModelOperatorApplication

def fix_all_teams():
    with app.app_context():
        print("🔧 Исправление команды для всех анкет...\n")
        
        try:
            # Получаем всех пользователей с командой
            users_with_team = User.query.filter(User.team != None, User.team != '').all()
            
            if not users_with_team:
                print("❌ Пользователей с командой не найдено")
                return
            
            print(f"📋 Найдено пользователей с командой: {len(users_with_team)}\n")
            
            total_fixed = 0
            
            for user in users_with_team:
                print(f"👤 Пользователь: {user.username} (команда: {user.team})")
                
                # Для анкет операторов
                applicants = Applicant.query.filter_by(owner_username=user.username).all()
                if applicants:
                    print(f"   Анкеты операторов: {len(applicants)}")
                    for app_rec in applicants:
                        if app_rec.team != user.team:
                            print(f"     - {app_rec.full_name}: '{app_rec.team}' → '{user.team}'")
                            app_rec.team = user.team
                            total_fixed += 1
                
                # Для анкет моделей/операторов
                models = ModelOperatorApplication.query.filter_by(owner_username=user.username).all()
                if models:
                    print(f"   Анкеты моделей: {len(models)}")
                    for model_rec in models:
                        if model_rec.team != user.team:
                            print(f"     - {model_rec.full_name}: '{model_rec.team}' → '{user.team}'")
                            model_rec.team = user.team
                            total_fixed += 1
                
                if not applicants and not models:
                    print(f"   ℹ️  Анкет от этого пользователя не найдено")
                
                print()
            
            if total_fixed > 0:
                db.session.commit()
                print(f"✅ Исправление завершено! Обновлено {total_fixed} анкет")
            else:
                print(f"✅ Все команды уже установлены правильно! Зафиксировано 0 ошибок")
            
        except Exception as e:
            print(f"❌ Ошибка: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    fix_all_teams()
