#!/bin/bash
# 🚀 Скрипт для быстрого deployment на Heroku

echo "🌐 Ray Squad Deployment Script"
echo "================================"

# Проверка Git
if ! command -v git &> /dev/null; then
    echo "❌ Git не установлен. Установите его первым."
    exit 1
fi

# Проверка Heroku CLI
if ! command -v heroku &> /dev/null; then
    echo "⚠️ Heroku CLI не установлен."
    echo "📥 Скачайте с: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Инициализация Git если нужно
if [ ! -d .git ]; then
    echo "📦 Инициализация Git репозитория..."
    git init
    git add .
    git commit -m "Initial commit for deployment"
fi

# Логин в Heroku
echo "🔑 Логинимся в Heroku..."
heroku login

# Создание приложения
read -p "📝 Введите название приложения на Heroku: " app_name

echo "🚀 Создаю приложение '$app_name' на Heroku..."
heroku create $app_name

# Установка переменных окружения
echo "⚙️ Устанавливаю конфигурацию..."
read -p "🔐 Введите SECRET_KEY (оставьте пусто для автогенерации): " secret_key

if [ -z "$secret_key" ]; then
    secret_key=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    echo "✅ Сгенерирован SECRET_KEY: $secret_key"
fi

heroku config:set FLASK_ENV=production
heroku config:set SECRET_KEY=$secret_key

# Deployment
echo "📤 Загружаю код на Heroku..."
git push heroku main

# Миграции БД
echo "🔄 Применяю миграции БД..."
heroku run python migrate_db.py

echo ""
echo "✅ Deployment завершен!"
echo "🌐 Ваш сайт доступен: https://$app_name.herokuapp.com"
echo ""
echo "📝 Для подключения собственного домена:"
echo "   1. heroku domains:add yourdomain.com"
echo "   2. Добавьте DNS запись в регистратор домена"
