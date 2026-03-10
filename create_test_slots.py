# -*- coding: utf-8 -*-
from app import app, db, InterviewSlot
from datetime import datetime, timedelta

with app.app_context():
    # Удаляем все старые слоты
    InterviewSlot.query.delete()
    db.session.commit()
    print('🗑️ Старые слоты удалены')
    
    # Создаём слоты для ОПЕРАТОРА на 5 марта 2026
    operator_date = datetime(2026, 3, 5)
    for hour in [12, 13, 14]:
        slot = InterviewSlot(
            start_time=datetime(2026, 3, 5, hour, 0, 0),
            end_time=datetime(2026, 3, 5, hour + 1, 0, 0),
            is_open=True,
            slot_type='operator'
        )
        db.session.add(slot)
        print(f'✅ Создан слот ОПЕРАТОРА: 5 марта {hour}:00-{hour+1}:00')
    
    # Создаём слоты для МОДЕЛИ на 7 марта 2026
    for hour in [15, 16, 17, 18]:
        slot = InterviewSlot(
            start_time=datetime(2026, 3, 7, hour, 0, 0),
            end_time=datetime(2026, 3, 7, hour + 1, 0, 0),
            is_open=True,
            slot_type='model'
        )
        db.session.add(slot)
        print(f'✅ Создан слот МОДЕЛИ: 7 марта {hour}:00-{hour+1}:00')
    
    # Создаём ещё слоты для ОПЕРАТОРА на 14 марта 2026
    for hour in [14, 15]:
        slot = InterviewSlot(
            start_time=datetime(2026, 3, 14, hour, 0, 0),
            end_time=datetime(2026, 3, 14, hour + 1, 0, 0),
            is_open=True,
            slot_type='operator'
        )
        db.session.add(slot)
        print(f'✅ Создан слот ОПЕРАТОРА: 14 марта {hour}:00-{hour+1}:00')
    
    # Создаём ещё слоты для МОДЕЛИ на 15 марта 2026
    for hour in [12, 13]:
        slot = InterviewSlot(
            start_time=datetime(2026, 3, 15, hour, 0, 0),
            end_time=datetime(2026, 3, 15, hour + 1, 0, 0),
            is_open=True,
            slot_type='model'
        )
        db.session.add(slot)
        print(f'✅ Создан слот МОДЕЛИ: 15 марта {hour}:00-{hour+1}:00')
    
    db.session.commit()
    
    print('\n' + '='*60)
    print('✅ ТЕСТОВЫЕ СЛОТЫ СОЗДАНЫ!')
    print('='*60)
    print('\n👨‍💼 ОПЕРАТОР:')
    print('  ✅ 5 марта: 12:00-13:00, 13:00-14:00, 14:00-15:00')
    print('  ✅ 14 марта: 14:00-15:00, 15:00-16:00')
    print('\n👩‍🎬 МОДЕЛЬ:')
    print('  ✅ 7 марта: 15:00-16:00, 16:00-17:00, 17:00-18:00, 18:00-19:00')
    print('  ✅ 15 марта: 12:00-13:00, 13:00-14:00')
    print('\n' + '='*60)
    print('Теперь обновите страницу и переключайтесь между вкладками!')
    print('='*60)
