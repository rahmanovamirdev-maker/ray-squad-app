#!/bin/bash
# Автоматическая установка TELEGRAM_BOT_TOKEN

echo "🔧 Установка TELEGRAM_BOT_TOKEN..."
echo ""

TOKEN="8605769417:AAGZYxU7g5pKQQQhMtWE5iiDJjK_E6aOXrI"

# Создаем .env файл
echo "Создаем .env файл..."
echo "TELEGRAM_BOT_TOKEN=$TOKEN" > .env
echo "SECRET_KEY=dev_secret_key" >> .env

echo "✅ Файл .env создан!"
echo ""
echo "📄 Содержимое .env:"
cat .env
echo ""
echo "✅ Готово! Теперь перезапустите приложение:"
echo "   systemctl restart ваш-сервис"
echo "   или: pkill -f 'python.*app.py' && python3 app.py"
echo ""
echo "Затем запустите диагностику:"
echo "   python3 diagnose_telegram_full.py"
