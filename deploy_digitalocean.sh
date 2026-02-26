#!/bin/bash
# 🚀 Скрипт для деплоя на DigitalOcean

echo "🌐 Ray Squad DigitalOcean Deployment"
echo "===================================="

# НАСТРОЙКИ - ИЗМЕНИТЕ ПОД ВАШИ ДАННЫЕ
SERVER_USER="root"  # или ваш пользователь на сервере
SERVER_IP="YOUR_SERVER_IP"  # IP адрес вашего сервера
PROJECT_DIR="/var/www/ray-squad-app"  # путь к проекту на сервере
APP_NAME="ray-squad"  # название приложения для systemd

echo "📡 Подключаюсь к серверу $SERVER_IP..."

ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
    echo "📂 Перехожу в директорию проекта..."
    cd /var/www/ray-squad-app || exit 1
    
    echo "⬇️ Получаю последние изменения из GitHub..."
    git pull origin main
    
    echo "📦 Устанавливаю зависимости..."
    source venv/bin/activate
    pip install -r requirements.txt
    
    echo "🔄 Перезапускаю приложение..."
    sudo systemctl restart ray-squad
    
    echo "✅ Деплой завершен!"
    echo "📊 Статус приложения:"
    sudo systemctl status ray-squad --no-pager
ENDSSH

echo ""
echo "🎉 Деплой на DigitalOcean завершен!"
