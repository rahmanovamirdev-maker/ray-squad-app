"""
Исправление команды для анкет Rey Squad которые были созданы 
от пользователей promisenothing и escobar
"""

from app import app, db, Applicant, ModelOperatorApplication

def fix_rey_squad_team():
    with app.app_context():
        print("🔧 Исправление команды для анкет Rey Squad...")
        
        try:
            rey_users = ['promisenothing', 'escobar']
            total_fixed = 0
            
            # Для операторов
            print("\n📋 Обработка анкет операторов:")
            amir_applicants = Applicant.query.filter(Applicant.owner_username.in_(rey_users)).all()
            print(f"Найдено {len(amir_applicants)} анкет операторов от пользователей Rey")
            
            for app_rec in amir_applicants:
                print(f"  Изменил: {app_rec.full_name} (ID: {app_rec.id})")
                print(f"    Owner: {app_rec.owner_username}")
                print(f"    Было: team='{app_rec.team}'")
                app_rec.team = 'Rey'
                print(f"    Стало: team='Rey'")
                total_fixed += 1
            
            if amir_applicants:
                db.session.commit()
                print(f"✓ Обновлено {len(amir_applicants)} анкет операторов")
            
            # Для моделей/операторов
            print("\n🎥 Обработка анкет моделей:")
            amir_models = ModelOperatorApplication.query.filter(ModelOperatorApplication.owner_username.in_(rey_users)).all()
            print(f"Найдено {len(amir_models)} анкет моделей от пользователей Rey")
            
            for model_rec in amir_models:
                print(f"  Изменил: {model_rec.full_name} (ID: {model_rec.id})")
                print(f"    Owner: {model_rec.owner_username}")
                print(f"    Было: team='{model_rec.team}'")
                model_rec.team = 'Rey'
                print(f"    Стало: team='Rey'")
                total_fixed += 1
            
            if amir_models:
                db.session.commit()
                print(f"✓ Обновлено {len(amir_models)} анкет моделей")
            
            print(f"\n✅ Исправление завершено! Всего обновлено: {total_fixed} анкет")
            
        except Exception as e:
            print(f"❌ Ошибка: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    fix_rey_squad_team()
