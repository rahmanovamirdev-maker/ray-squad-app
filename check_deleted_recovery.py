#!/usr/bin/env python3
"""Диагностика удаленных анкет на production"""

from app import app, db
from datetime import datetime, timedelta

with app.app_context():
    print("=" * 80)
    print("ДИАГНОСТИКА: Что осталось в БД и как восстановить")
    print("=" * 80)
    
    from app import ModelOperatorApplication, ChatApplication, Applicant
    
    # 1. Текущее состояние БД
    print("\n1️⃣  ТЕКУЩЕЕ СОСТОЯНИЕ БД:")
    models = ModelOperatorApplication.query.all()
    chatters = ChatApplication.query.all()
    applicants = Applicant.query.all()
    
    print(f"   Моделей: {len(models)}")
    print(f"   Чаттеров: {len(chatters)}")
    print(f"   Операторов: {len(applicants)}")
    
    # 2. Проверяем какие анкеты are_deleted
    print("\n2️⃣  СОСТОЯНИЕ МЯГКОГО УДАЛЕНИЯ:")
    deleted_models = ModelOperatorApplication.query.filter_by(is_deleted=True).count()
    deleted_chatters = ChatApplication.query.filter_by(is_deleted=True).count()
    deleted_applicants = Applicant.query.filter_by(is_deleted=True).count()
    
    print(f"   Удаленных моделей (is_deleted=True): {deleted_models}")
    print(f"   Удаленных чаттеров (is_deleted=True): {deleted_chatters}")
    print(f"   Удаленных операторов (is_deleted=True): {deleted_applicants}")
    
    # 3. Проверяем дату добавления (может найти недавно удаленные)
    print("\n3️⃣  АНКЕТЫ ПО ДАТАМ ДОБАВЛЕНИЯ:")
    today = datetime.now()
    one_week_ago = today - timedelta(days=7)
    
    fresh_models = ModelOperatorApplication.query.filter(
        ModelOperatorApplication.date_added >= one_week_ago
    ).all()
    print(f"   Моделей добавлено за неделю: {len(fresh_models)}")
    if fresh_models:
        for m in fresh_models[:3]:
            status = "❌ Удалена" if m.is_deleted else "✅ Активна"
            print(f"     - {m.full_name} ({m.date_added.strftime('%d.%m.%Y')}) {status}")
    
    # 4. Проверяем backup файлы
    import os
    import glob
    
    print("\n4️⃣  ПОИСК BACKUP ФАЙЛОВ БД:")
    backup_patterns = [
        'database*.db*',
        'backup*.db*',
        '*.db.bak',
        '*.db.backup',
        'instance/database*.db*'
    ]
    
    found_backups = []
    for pattern in backup_patterns:
        found_backups.extend(glob.glob(pattern))
    
    if found_backups:
        print(f"   ✅ Найдено {len(found_backups)} файлов backup:")
        for backup in found_backups:
            size_mb = os.path.getsize(backup) / (1024*1024)
            print(f"     - {backup} ({size_mb:.2f} MB)")
    else:
        print("   ❌ Backup файлов не найдено")
    
    print("\n" + "=" * 80)
    print("ИНСТРУКЦИЯ ВОССТАНОВЛЕНИЯ:")
    print("=" * 80)
    print("""
1. ЕСЛИ ЕСТЬ BACKUP:
   - Сделай копию текущей БД: cp instance/database.db instance/database.db.corrupted
   - Восстанови из backup: cp backup-file.db instance/database.db
   - Перезагрузи сайт

2. ЕСЛИ BACKUP НА СЕРВЕРЕ (в /backups или подобное):
   - Спроси у хостера/администратора
   - Обычно есть daily/weekly backups

3. ЕСЛИ НЕТУ НИКАКИХ BACKUP:
   - Данные безвозвратно потеряны
   - Можно только заново добавить анкеты вручную или импортировать из другого источника

4. КАК ЭТОГО ИЗБЕЖАТЬ В БУДУЩЕМ:
   - Теперь использую мягкое удаление (is_deleted флаг)
   - Записи в архиве НЕ удаляются никогда
   - Плюс бэкапируй БД регулярно!
    """)
    
    print("=" * 80)

if __name__ == '__main__':
    pass
