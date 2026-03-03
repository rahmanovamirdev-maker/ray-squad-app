#!/usr/bin/env python3
"""
ПОЛНАЯ диагностика Telegram бота
Проверяет ВСЕ: библиотеку, токен, соединение, .env файл
"""
import os
import sys

print("=" * 90)
print("🔍 ПОЛНАЯ ДИАГНОСТИКА TELEGRAM БОТА")
print("=" * 90)
print()

# ========== ПРОВЕРКА 1: БИБЛИОТЕКА ==========
print("1️⃣  Проверка библиотеки python-telegram-bot...")
try:
    from telegram import Bot
    from telegram.error import TelegramError
    import telegram
    print(f"   ✅ Библиотека установлена: версия {telegram.__version__}")
    LIBRARY_OK = True
except ImportError as e:
    print(f"   ❌ Библиотека НЕ установлена!")
    print(f"   Ошибка: {e}")
    print()
    print("   📌 ИСПРАВЛЕНИЕ:")
    print("   pip3 install python-telegram-bot==21.0.1")
    print("   или: pip install -r requirements.txt")
    LIBRARY_OK = False
    sys.exit(1)

print()

# ========== ПРОВЕРКА 2: TELEGRAM_BOT_TOKEN ==========
print("2️⃣  Проверка TELEGRAM_BOT_TOKEN в переменных окружения...")
TOKEN_FROM_ENV = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
TOKEN_FROM_DOTENV = ''
FINAL_TOKEN = ''

if TOKEN_FROM_ENV:
    print(f"   ✅ Найден в переменных окружения: {TOKEN_FROM_ENV[:25]}...{TOKEN_FROM_ENV[-8:]}")
    FINAL_TOKEN = TOKEN_FROM_ENV
else:
    print("   ❌ НЕ найден в переменных окружения (os.environ)")

# Проверяем .env файл
if os.path.exists('.env'):
    print("   📄 Проверяем .env файл...")
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    TOKEN_FROM_DOTENV = line.split('=', 1)[1].strip().strip('"').strip("'")
                    print(f"   ✅ Найден в .env: {TOKEN_FROM_DOTENV[:25]}...{TOKEN_FROM_DOTENV[-8:]}")
                    if not FINAL_TOKEN:
                        FINAL_TOKEN = TOKEN_FROM_DOTENV
                    break
        if not TOKEN_FROM_DOTENV:
            print("   ⚠️  .env файл существует, но TELEGRAM_BOT_TOKEN не найден")
    except Exception as e:
        print(f"   ⚠️  Ошибка чтения .env: {e}")
else:
    print("   ⚠️  Файл .env не найден")

# Используем токен по умолчанию для тестирования
if not FINAL_TOKEN:
    print()
    print("   ❌ ТОКЕН НЕ НАЙДЕН НИГДЕ!")
    print()
    print("   📌 ИСПРАВЛЕНИЕ - выберите один из способов:")
    print()
    print("   СПОСОБ 1 - Создать .env файл (РЕКОМЕНДУЕТСЯ):")
    print("   " + "-" * 60)
    print('   echo "TELEGRAM_BOT_TOKEN=8605769417:AAGZYxU7g5pKQQQhMtWE5iiDJjK_E6aOXrI" > .env')
    print()
    print("   СПОСОБ 2 - Установить переменную окружения в текущей сессии:")
    print("   " + "-" * 60)
    print('   export TELEGRAM_BOT_TOKEN="8605769417:AAGZYxU7g5pKQQQhMtWE5iiDJjK_E6aOXrI"')
    print()
    print("   СПОСОБ 3 - Для systemd сервиса (в /etc/systemd/system/ваш-сервис.service):")
    print("   " + "-" * 60)
    print("   [Service]")
    print('   Environment="TELEGRAM_BOT_TOKEN=8605769417:AAGZYxU7g5pKQQQhMtWE5iiDJjK_E6aOXrI"')
    print("   Потом: systemctl daemon-reload && systemctl restart ваш-сервис")
    print()
    print("   ⚠️  Для продолжения диагностики используем токен по умолчанию...")
    FINAL_TOKEN = '8605769417:AAGZYxU7g5pKQQQhMtWE5iiDJjK_E6aOXrI'
else:
    print()
    print(f"   ✅ ИТОГ: Будем использовать токен: {FINAL_TOKEN[:25]}...{FINAL_TOKEN[-8:]}")

print()

# ========== ПРОВЕРКА 3: TELEGRAM API ==========
print("3️⃣  Проверка соединения с Telegram API...")
import asyncio

async def test_connection():
    try:
        bot = Bot(token=FINAL_TOKEN)
        me = await bot.get_me()
        return True, me, None
    except TelegramError as e:
        return False, None, f"Telegram ошибка: {e}"
    except Exception as e:
        return False, None, f"Неожиданная ошибка: {e}"

try:
    success, bot_info, error = asyncio.run(test_connection())
    
    if success:
        print(f"   ✅ Подключение успешно!")
        print(f"   🤖 Имя бота: {bot_info.first_name}")
        print(f"   🔗 Username: @{bot_info.username}")
        print(f"   🆔 Bot ID: {bot_info.id}")
    else:
        print(f"   ❌ Не удалось подключиться к Telegram API")
        print(f"   Ошибка: {error}")
        if "401" in str(error) or "Unauthorized" in str(error):
            print()
            print("   📌 Токен недействителен! Проверьте правильность токена.")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Критическая ошибка: {e}")
    sys.exit(1)

print()

# ========== ПРОВЕРКА 4: UPDATES (ЕСТЬ ЛИ ДИАЛОГИ) ==========
print("4️⃣  Проверка updates (есть ли пользователи, которые писали боту)...")

async def check_updates():
    try:
        bot = Bot(token=FINAL_TOKEN)
        updates = await bot.get_updates(limit=100, timeout=5)
        return True, updates, None
    except Exception as e:
        return False, [], str(e)

try:
    success, updates, error = asyncio.run(check_updates())
    
    if success:
        if updates:
            print(f"   ✅ Найдено {len(updates)} updates")
            
            # Собираем уникальные чаты
            unique_chats = {}
            for upd in updates:
                msg = upd.message or upd.edited_message
                if msg and msg.chat and msg.chat.type == 'private':
                    chat_id = msg.chat.id
                    username = msg.chat.username or msg.from_user.username if msg.from_user else None
                    unique_chats[chat_id] = username
            
            if unique_chats:
                print(f"   📊 Уникальных чатов (users): {len(unique_chats)}")
                print()
                print("   👥 Список пользователей:")
                for chat_id, username in unique_chats.items():
                    user_str = f"@{username}" if username else "(без username)"
                    print(f"      • Chat ID: {chat_id} — {user_str}")
            else:
                print("   ⚠️  Updates есть, но нет приватных чатов")
        else:
            print("   ⚠️  Updates пусты — НИКТО НЕ ПИСАЛ БОТУ!")
            print()
            print("   📌 ЧТО ДЕЛАТЬ:")
            print(f"   1. Откройте Telegram и найдите бота (если знаете username)")
            print("   2. Напишите боту /start")
            print("   3. Снова запустите эту диагностику")
    else:
        print(f"   ❌ Ошибка получения updates: {error}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print()

# ========== ПРОВЕРКА 5: БАЗА ДАННЫХ ==========
print("5️⃣  Проверка базы данных...")

if os.path.exists('instance/database.db'):
    db_path = 'instance/database.db'
elif os.path.exists('database.db'):
    db_path = 'database.db'
else:
    print("   ⚠️  База данных не найдена")
    db_path = None

if db_path:
    print(f"   ✅ База данных: {db_path}")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем таблицу scout_join_application
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scout_join_application'")
        if cursor.fetchone():
            print("   ✅ Таблица scout_join_application существует")
            
            # Проверяем есть ли колонка telegram_chat_id
            cursor.execute("PRAGMA table_info(scout_join_application)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'telegram_chat_id' in columns:
                print("   ✅ Колонка telegram_chat_id существует")
                
                # Считаем скаутов с chat_id
                cursor.execute("SELECT COUNT(*) FROM scout_join_application")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM scout_join_application WHERE telegram_chat_id IS NOT NULL AND telegram_chat_id != ''")
                with_chat_id = cursor.fetchone()[0]
                
                print(f"   📊 Всего заявок скаутов: {total}")
                print(f"   📊 С сохраненным chat_id: {with_chat_id}")
                
                if with_chat_id > 0:
                    cursor.execute("SELECT telegram_username, telegram_chat_id FROM scout_join_application WHERE telegram_chat_id IS NOT NULL AND telegram_chat_id != '' LIMIT 5")
                    print()
                    print("   📋 Примеры:")
                    for row in cursor.fetchall():
                        print(f"      • {row[0]} → chat_id: {row[1]}")
            else:
                print("   ❌ Колонка telegram_chat_id НЕ существует!")
                print("   📌 Запустите миграцию или пересоздайте БД")
        else:
            print("   ⚠️  Таблица scout_join_application не найдена")
        
        conn.close()
    except Exception as e:
        print(f"   ❌ Ошибка доступа к БД: {e}")

print()
print("=" * 90)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 90)
print()

if not TOKEN_FROM_ENV and not TOKEN_FROM_DOTENV:
    print("⚠️  ГЛАВНАЯ ПРОБЛЕМА: TELEGRAM_BOT_TOKEN не установлен!")
    print("📌 Установите токен одним из способов выше и перезапустите приложение")
elif not updates:
    print("⚠️  БОТ РАБОТАЕТ, НО НИКТО НЕ ПИСАЛ ЕМУ /start")
    print("📌 Попросите пользователя написать боту /start перед подачей заявки")
else:
    print("✅ ВСЕ КОМПОНЕНТЫ В ПОРЯДКЕ!")
    print("📌 Telegram уведомления должны работать")
