# -*- coding: utf-8 -*-
from app import app, db, InterviewSlot

with app.app_context():
    slots = InterviewSlot.query.all()
    print(f'📊 Всего слотов в базе: {len(slots)}')
    
    if slots:
        operator_slots = [s for s in slots if s.slot_type == 'operator']
        model_slots = [s for s in slots if s.slot_type == 'model']
        null_slots = [s for s in slots if s.slot_type is None or s.slot_type == '']
        
        print(f'👨‍💼 Слотов для ОПЕРАТОРА: {len(operator_slots)}')
        print(f'👩‍🎬 Слотов для МОДЕЛИ: {len(model_slots)}')
        print(f'❓ Слотов БЕЗ ТИПА (NULL): {len(null_slots)}')
        
        print('\n📋 Первые 10 слотов:')
        for s in slots[:10]:
            print(f'  ID={s.id}, start={s.start_time}, type="{s.slot_type}", is_open={s.is_open}')
    else:
        print('❌ База данных ПУСТАЯ - слотов нет!')
