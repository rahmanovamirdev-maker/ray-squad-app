#!/usr/bin/env python3
"""Скрипт для обновления команды Amir на ХАЦКЕР для всех пользователей и заявок"""

from app import app, db, User, Applicant, ModelOperatorApplication, ChatApplication

def migrate_teams():
    """Заменить Amir на ХАЦКЕР во всех таблицах"""
    
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ: Замена Amir на ХАЦКЕР")
        print("=" * 80)
        
        # 1. Обновление пользователей
        print("\n1. Обновление таблицы User...")
        users_count = User.query.filter_by(team='Amir').count()
        if users_count > 0:
            User.query.filter_by(team='Amir').update({'team': 'ХАЦКЕР'})
            print(f"   ✓ Обновлено пользователей: {users_count}")
        else:
            print(f"   ✓ Пользователей с командой Amir не найдено")
        
        # 2. Обновление операторских заявок
        print("\n2. Обновление таблицы Applicant...")
        applicants_count = Applicant.query.filter_by(team='Amir').count()
        if applicants_count > 0:
            Applicant.query.filter_by(team='Amir').update({'team': 'ХАЦКЕР'})
            print(f"   ✓ Обновлено заявок операторов: {applicants_count}")
        else:
            print(f"   ✓ Заявок операторов с командой Amir не найдено")
        
        # 3. Обновление заявок моделей
        print("\n3. Обновление таблицы ModelOperatorApplication...")
        models_count = ModelOperatorApplication.query.filter_by(team='Amir').count()
        if models_count > 0:
            ModelOperatorApplication.query.filter_by(team='Amir').update({'team': 'ХАЦКЕР'})
            print(f"   ✓ Обновлено заявок моделей: {models_count}")
        else:
            print(f"   ✓ Заявок моделей с командой Amir не найдено")
        
        # 4. Обновление заявок чаттеров
        print("\n4. Обновление таблицы ChatApplication...")
        chatters_count = ChatApplication.query.filter_by(team='Amir').count()
        if chatters_count > 0:
            ChatApplication.query.filter_by(team='Amir').update({'team': 'ХАЦКЕР'})
            print(f"   ✓ Обновлено заявок чаттеров: {chatters_count}")
        else:
            print(f"   ✓ Заявок чаттеров с командой Amir не найдено")
        
        # Сохранение изменений
        db.session.commit()
        
        print("\n" + "=" * 80)
        print("УСПЕШНО! Все вхождения Amir заменены на ХАЦКЕР")
        total = users_count + applicants_count + models_count + chatters_count
        print(f"Всего обновлено записей: {total}")
        print("=" * 80)

if __name__ == '__main__':
    migrate_teams()
