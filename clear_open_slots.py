"""
Скрипт для удаления всех открытых слотов из базы данных
"""
from app import app, db, InterviewSlot

with app.app_context():
    # Получаем все открытые слоты
    open_slots = InterviewSlot.query.filter_by(is_open=True).all()
    count = len(open_slots)
    
    print(f"🔍 Найдено открытых слотов: {count}")
    
    if count > 0:
        # Удаляем все открытые слоты
        for slot in open_slots:
            db.session.delete(slot)
        
        db.session.commit()
        print(f"✅ Успешно удалено {count} открытых слотов")
    else:
        print("ℹ️ Нет открытых слотов для удаления")
