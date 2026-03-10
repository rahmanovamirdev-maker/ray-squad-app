#!/usr/bin/env python3
"""Диагностика endpoint архива"""

from app import app, db, User, Applicant, ModelOperatorApplication, ChatApplication
import json

with app.app_context():
    print("=" * 80)
    print("ДИАГНОСТИКА АРХИВА")
    print("=" * 80)
    
    # Найти админа
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        print("❌ Нет админа в БД!")
        exit(1)
    
    print(f"✅ Админ найден: {admin.username} (ID: {admin.id})")
    
    # Тестируем endpoint с сессией
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = admin.id
        
        print("\n🔄 Отправляю запрос к /api/admin/applicants-full-archive...")
        response = client.get('/api/admin/applicants-full-archive')
        
        print(f"📊 HTTP Status: {response.status_code}")
        
        data = response.get_json()
        
        print("\n📦 ОТВЕТ ENDPOINT:")
        print(f"  success: {data.get('success')}")
        if not data.get('success'):
            print(f"  ❌ ERROR MESSAGE: {data.get('message')}")
        print(f"  total_count: {data.get('total_count')}")
        print(f"  operators_count: {data.get('operators_count')}")
        print(f"  models_count: {data.get('models_count')}")
        print(f"  chatters_count: {data.get('chatters_count')}")
        print(f"  applicants: {len(data.get('applicants', []))} записей")
        
        # Проверяем каждую запись
        if data.get('applicants'):
            print("\n📋 ДЕТАЛИ ЗАПИСЕЙ:")
            for i, app_item in enumerate(data['applicants'][:2]):  # Первые 2
                print(f"\n  Запись {i+1}:")
                print(f"    type: {app_item.get('type')}")
                print(f"    full_name: {app_item.get('full_name')}")
                print(f"    is_deleted: {app_item.get('is_deleted')}")
                print(f"    status: {app_item.get('status')}")
                print(f"    date_added: {app_item.get('date_added')}")
        else:
            print("\n❌ Порблема: data.applicants пуста или отсутствует!")
            print(f"    data.applicants = {data.get('applicants')}")
            print(f"    type: {type(data.get('applicants'))}")
        
        # Также тестируем прямой запрос к БД
        print("\n" + "=" * 80)
        print("ПРЯМАЯ ПРОВЕРКА БД:")
        print("=" * 80)
        
        all_applicants = Applicant.query.all()
        all_models = ModelOperatorApplication.query.all()
        all_chatters = ChatApplication.query.all()
        
        print(f"\nОператоры (Applicant): {len(all_applicants)}")
        for app in all_applicants[:2]:
            print(f"  - {app.full_name} (is_deleted: {getattr(app, 'is_deleted', 'NO FIELD')})")
        
        print(f"\nМодели (ModelOperatorApplication): {len(all_models)}")
        for model in all_models[:2]:
            print(f"  - {model.full_name} (is_deleted: {model.is_deleted})")
        
        print(f"\nЧаттеры (ChatApplication): {len(all_chatters)}")
        for chatter in all_chatters[:2]:
            print(f"  - {chatter.full_name} (is_deleted: {getattr(chatter, 'is_deleted', 'NO FIELD')})")

print("\n" + "=" * 80)
