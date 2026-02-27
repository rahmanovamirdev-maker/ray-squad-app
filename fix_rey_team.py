"""
Исправление команды для анкет Rey Squad которые были созданы с owner_username=Amir
"""

from app import app, db, Applicant, ModelOperatorApplication

def fix_rey_squad_team():
    with app.app_context():
        print("🔧 Исправление команды для анкет Rey Squad...")
        
        try:
            # Находим все анкеты где owner_username = "amir" и меняем team на "Rey"
            # Сначала для операторов
            amir_applicants = Applicant.query.filter_by(owner_username='amir').all()
            print(f"Найдено {len(amir_applicants)} анкет операторов с owner_username='amir'")
            
            for app_rec in amir_applicants:
                print(f"  Изменил: {app_rec.full_name} (ID: {app_rec.id})")
                print(f"    Было: team='{app_rec.team}'")
                app_rec.team = 'Rey'
                print(f"    Стало: team='Rey'")
            
            if amir_applicants:
                db.session.commit()
                print(f"✓ Обновлено {len(amir_applicants)} анкет операторов")
            
            # Теперь для моделей/операторов
            amir_models = ModelOperatorApplication.query.filter_by(owner_username='amir').all()
            print(f"Найдено {len(amir_models)} анкет моделей с owner_username='amir'")
            
            for model_rec in amir_models:
                print(f"  Изменил: {model_rec.full_name} (ID: {model_rec.id})")
                print(f"    Было: team='{model_rec.team}'")
                model_rec.team = 'Rey'
                print(f"    Стало: team='Rey'")
            
            if amir_models:
                db.session.commit()
                print(f"✓ Обновлено {len(amir_models)} анкет моделей")
            
            print("\n✅ Исправление завершено!")
            
        except Exception as e:
            print(f"❌ Ошибка: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    fix_rey_squad_team()
