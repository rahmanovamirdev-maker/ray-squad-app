# 🚨 СРОЧНОЕ ИСПРАВЛЕНИЕ: Полный архив не работает

## ❌ Проблема
Вкладка "📚 Полный архив" в админ-панели возвращает ошибку 400.
В таблице `scout_join_application` отсутствуют обязательные поля `team` и `is_deleted`.

## ✅ Решение

### Что исправлено:
1. ✅ Добавлено поле `is_deleted` в модель `ScoutJoinApplication`
2. ✅ Добавлены поля `team` и `is_deleted` в метод `to_dict()`
3. ✅ Создан миграционный скрипт `migrate_scout_is_deleted.py`

### Локальное тестирование:
```bash
python migrate_scout_is_deleted.py  # ✅ Успешно
python debug_archive.py             # ✅ Status 200, архив работает
```

---

## 🚀 РАЗВЁРТЫВАНИЕ НА PRODUCTION

### Вариант 1: Через GIT (рекомендуется)

```bash
# На локальной машине: закоммитить изменения
git add app.py migrate_scout_is_deleted.py
git commit -m "FIX: Добавлены поля team и is_deleted для ScoutJoinApplication"
git push origin main

# На сервере: обновить код
ssh root@your-server
cd /path/to/app
git pull origin main

# Создать бэкап БД
cp instance/database.db instance/database.db.backup_$(date +%Y%m%d_%H%M%S)

# Запустить миграцию
python3 migrate_scout_is_deleted.py

# Перезапустить приложение
sudo systemctl restart your-app  # или supervisor/gunicorn
```

### Вариант 2: Через SCP (если нет GIT)

```bash
# На локальной машине: скопировать файлы
scp app.py root@your-server:/path/to/app/
scp migrate_scout_is_deleted.py root@your-server:/path/to/app/

# На сервере: выполнить миграцию
ssh root@your-server
cd /path/to/app
cp instance/database.db instance/database.db.backup_$(date +%Y%m%d_%H%M%S)
python3 migrate_scout_is_deleted.py
sudo systemctl restart your-app
```

---

## 🔍 Проверка работы

1. Откройте админ-панель на боевом сайте
2. Перейдите на вкладку **"📚 Полный архив"**
3. Должны загрузиться все анкеты (операторы, модели, чаттеры, стримерши)
4. Откройте консоль браузера (F12) - не должно быть ошибок

---

## 📋 Изменённые файлы

| Файл | Что изменено |
|------|--------------|
| `app.py` | Добавлено поле `is_deleted` в модель `ScoutJoinApplication`<br>Обновлён метод `to_dict()` (добавлены `team`, `is_deleted`) |
| `migrate_scout_is_deleted.py` | Новый файл - миграция БД |
| `debug_archive.py` | Обновлён для вывода ошибок |

---

## 🆘 Если не работает

### 1. Проверить логи приложения
```bash
tail -f /var/log/your-app/error.log
# или
journalctl -u your-app -f
```

### 2. Проверить что миграция прошла
```bash
python3 migrate_scout_is_deleted.py
# Должно вывести:
# ✅ Столбец team успешно добавлен!
# ℹ️  Столбец is_deleted уже существует
```

### 3. Проверить структуру БД
```bash
sqlite3 instance/database.db
sqlite> .schema scout_join_application
# Должны быть поля team и is_deleted
```

### 4. Проверить в браузере (F12)
- Откройте консоль разработчика
- Перейдите на вкладку "Полный архив"
- Проверьте запрос `/api/admin/applicants-full-archive`
- Статус должен быть 200, а не 400

---

## ⚡ Быстрый деплой (одной командой)

Если у вас настроен SSH и известен путь:

```bash
# Замените YOUR_SERVER и /path/to/app на реальные значения
ssh YOUR_SERVER "cd /path/to/app && git pull && cp instance/database.db instance/database_backup.db && python3 migrate_scout_is_deleted.py && sudo systemctl restart your-app"
```

---

## 📞 Контакты
Если возникли проблемы при развёртывании - пишите в чат!
