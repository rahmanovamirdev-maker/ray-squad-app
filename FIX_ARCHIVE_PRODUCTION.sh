#!/bin/bash
# ===================================================================
# СРОЧНЫЙ FIX: Восстановление архива на production
# ===================================================================
# Проблема: Не работает полный архив - модель ScoutJoinApplication
#           не имела полей team и is_deleted в БД и to_dict()
# ===================================================================

echo "🔧 СРОЧНЫЙ FIX: Восстановление архива"
echo "====================================================="

# 1. Залогиниться на сервер
echo "1️⃣ Заходим на production сервер..."
# ssh root@your-server-ip

# 2. Перейти в директорию проекта
echo "2️⃣ Переходим в директорию проекта..."
# cd /path/to/your/app

# 3. ВАЖНО: Создать бэкап БД перед миграцией
echo "3️⃣ Создаём БЭКАП базы данных..."
echo "   cp instance/database.db instance/database.db.backup_$(date +%Y%m%d_%H%M%S)"

# 4. Скопировать файлы на сервер (с локальной машины)
echo ""
echo "4️⃣ Копируем файлы на сервер (выполнить с ЛОКАЛЬНОЙ машины):"
echo "   scp app.py root@your-server:/path/to/app/"
echo "   scp migrate_scout_is_deleted.py root@your-server:/path/to/app/"

# 5. Активировать виртуальное окружение (если есть)
echo ""
echo "5️⃣ Активируем виртуальное окружение (на сервере):"
echo "   source venv/bin/activate  # если используется venv"

# 6. Запустить миграцию
echo ""
echo "6️⃣ Запускаем миграцию базы данных:"
echo "   python3 migrate_scout_is_deleted.py"

# 7. Перезапустить приложение
echo ""
echo "7️⃣ Перезапускаем приложение:"
echo "   # Для systemd:"
echo "   sudo systemctl restart your-app-name"
echo ""
echo "   # Для supervisor:"
echo "   sudo supervisorctl restart your-app-name"
echo ""
echo "   # Для tmux/screen (если запущено вручную):"
echo "   # Найти процесс: ps aux | grep python"
echo "   # Убить: kill -9 PID"
echo "   # Запустить заново: python3 app.py &"

# 8. Проверить работу
echo ""
echo "8️⃣ Проверяем работу архива:"
echo "   - Откройте админ-панель"
echo "   - Перейдите на вкладку '📚 Полный архив'"
echo "   - Убедитесь что данные загружаются"

echo ""
echo "====================================================="
echo "✅ DONE! Проверьте архив на сайте"
echo "====================================================="
echo ""
echo "📋 ЧТО БЫЛО ИСПРАВЛЕНО:"
echo "  1. Добавлено поле is_deleted в модель ScoutJoinApplication"
echo "  2. Добавлено поле team в базу данных scout_join_application"
echo "  3. Обновлён метод to_dict() с полями team и is_deleted"
echo ""
echo "🔍 ЕСЛИ НЕ РАБОТАЕТ:"
echo "  1. Проверьте логи: tail -f /var/log/your-app/error.log"
echo "  2. Проверьте что миграция прошла успешно"
echo "  3. Убедитесь что приложение перезапущено"
echo "  4. Откройте консоль браузера (F12) и проверьте ошибки"
