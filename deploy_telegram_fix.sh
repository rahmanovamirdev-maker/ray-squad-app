#!/bin/bash
# Скрипт для установки Telegram зависимостей и перезапуска сервиса

echo "🔄 Установка python-telegram-bot..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Зависимости установлены успешно"
else
    echo "❌ Ошибка при установке зависимостей"
    exit 1
fi

echo ""
echo "🔍 Запуск диагностики..."
python3 diagnose_telegram.py

echo ""
echo "🔄 Перезапуск приложения..."
# Найдем и перезапустим Flask процесс
if systemctl list-units --type=service | grep -q flask; then
    SERVICE_NAME=$(systemctl list-units --type=service | grep flask | awk '{print $1}')
    echo "Найден сервис: $SERVICE_NAME"
    systemctl restart $SERVICE_NAME
    echo "✅ Сервис перезапущен"
elif pgrep -f "gunicorn.*app:app" > /dev/null; then
    echo "Найден gunicorn процесс, перезапускаем..."
    pkill -f "gunicorn.*app:app"
    sleep 2
    gunicorn --bind 0.0.0.0:8000 app:app --daemon
    echo "✅ Gunicorn перезапущен"
elif pgrep -f "python.*app.py" > /dev/null; then
    echo "Найден python процесс, перезапускаем..."
    pkill -f "python.*app.py"
    sleep 2
    nohup python3 app.py > /dev/null 2>&1 &
    echo "✅ Python процесс перезапущен"
else
    echo "⚠️ Не найден запущенный Flask сервис"
    echo "Запустите приложение вручную"
fi

echo ""
echo "✅ Готово! Теперь проверьте Telegram уведомления"
echo "Используйте: python3 test_telegram.py @username"
