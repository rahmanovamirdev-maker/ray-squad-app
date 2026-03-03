#!/usr/bin/env python3
"""Диагностика Telegram бота на production"""

import sys
import os

print("=" * 80)
print("ДИАГНОСТИКА TELEGRAM БОТА")
print("=" * 80)

# 1. Проверка импорта telegram библиотеки
print("\n1️⃣  Проверка установки python-telegram-bot...")
try:
    from telegram import Bot
    from telegram.error import TelegramError
    import telegram
    print(f"   ✅ Библиотека установлена: версия {telegram.__version__}")
except ImportError as e:
    print(f"   ❌ Библиотека НЕ установлена: {e}")
    print("   📌 Решение: pip install python-telegram-bot")
    sys.exit(1)

# 2. Проверка токена
print("\n2️⃣  Проверка токена бота...")
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8605769417:AAGZYyF8tOvhWwEqq8iO8SC8iCK08DwEZh0')

if not TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN) < 30:
    print(f"   ❌ Токен отсутствует или неполный")
    print(f"   📌 Текущий токен: {TELEGRAM_BOT_TOKEN[:20]}...")
    sys.exit(1)

print(f"   ✅ Токен найден: {TELEGRAM_BOT_TOKEN[:20]}...{TELEGRAM_BOT_TOKEN[-10:]}")

# 3. Проверка подключения к Telegram API
print("\n3️⃣  Проверка подключения к Telegram API...")
try:
    import asyncio
    
    async def test_bot_connection():
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        try:
            me = await bot.get_me()
            return True, me, None
        except Exception as e:
            return False, None, str(e)
    
    loop = asyncio.get_event_loop()
    success, me, error = loop.run_until_complete(test_bot_connection())
    
    if success:
        print(f"   ✅ Бот подключен: @{me.username} ({me.first_name})")
        print(f"   📝 ID бота: {me.id}")
    else:
        print(f"   ❌ Не удалось подключиться к боту: {error}")
        print("   📌 Проверьте токен или доступ к api.telegram.org")
        sys.exit(1)
        
except Exception as e:
    print(f"   ❌ Ошибка при проверке подключения: {e}")
    sys.exit(1)

# 4. Проверка наличия updates (диалогов)
print("\n4️⃣  Проверка наличия updates (сообщений боту)...")
try:
    async def check_updates():
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        try:
            updates = await bot.get_updates(limit=100, timeout=5)
            return updates
        except Exception as e:
            return None
    
    loop = asyncio.get_event_loop()
    updates = loop.run_until_complete(check_updates())
    
    if updates is None:
        print(f"   ⚠️  Не удалось получить updates")
    elif len(updates) == 0:
        print(f"   ⚠️  Updates пусты (никто не писал боту)")
        print("   📌 Для работы уведомлений кто-то должен написать боту /start")
    else:
        print(f"   ✅ Найдено {len(updates)} updates")
        
        # Показываем первые 5 чатов
        unique_chats = {}
        for update in updates:
            msg = update.message or update.edited_message
            if msg and msg.chat:
                chat_id = msg.chat.id
                username = msg.chat.username or msg.from_user.username if msg.from_user else None
                if chat_id not in unique_chats:
                    unique_chats[chat_id] = username
        
        print(f"   📋 Уникальных чатов: {len(unique_chats)}")
        for idx, (chat_id, username) in enumerate(list(unique_chats.items())[:5]):
            print(f"      {idx+1}. chat_id={chat_id}, username=@{username or 'unknown'}")
        
        if len(unique_chats) > 5:
            print(f"      ... и ещё {len(unique_chats) - 5} чатов")
            
except Exception as e:
    print(f"   ❌ Ошибка при проверке updates: {e}")

# 5. Тест отправки сообщения
print("\n5️⃣  Тест отправки сообщения...")
print("   ℹ️  Для теста нужен chat_id или username человека, который писал боту")
print("   ℹ️  Пропускаем автотест (запустите вручную через test_telegram.py)")

# 6. Проверка БД на наличие telegram_chat_id
print("\n6️⃣  Проверка БД на наличие сохраненных chat_id...")
try:
    from app import app, db, ScoutJoinApplication
    
    with app.app_context():
        scouts = ScoutJoinApplication.query.all()
        scouts_with_chat_id = [s for s in scouts if s.telegram_chat_id]
        
        print(f"   📊 Всего скаутов в БД: {len(scouts)}")
        print(f"   📊 С сохраненным chat_id: {len(scouts_with_chat_id)}")
        
        if scouts_with_chat_id:
            print(f"   ✅ Примеры:")
            for scout in scouts_with_chat_id[:3]:
                print(f"      - {scout.full_name}: chat_id={scout.telegram_chat_id}, username={scout.telegram_username}")
        else:
            print(f"   ⚠️  Ни у кого нет сохраненного chat_id")
            print(f"   📌 chat_id сохраняется автоматически при первой успешной отправке")
            
except Exception as e:
    print(f"   ⚠️  Не удалось проверить БД: {e}")

print("\n" + "=" * 80)
print("ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
print("=" * 80)

recommendations = []

if 'updates' in locals() and updates is not None and len(updates) == 0:
    recommendations.append("1. Попросите тестового пользователя написать боту /start в личку")
    recommendations.append("2. После этого заполните форму на сайте с его telegram username")

if 'scouts' in locals() and len(scouts) > 0 and len(scouts_with_chat_id) == 0:
    recommendations.append("3. У всех скаутов отсутствует chat_id - значит отправка ни разу не удавалась")
    recommendations.append("4. Проверьте что люди писали боту /start ПЕРЕД заполнением формы")

recommendations.append("5. Для ручного теста: используйте test_telegram.py с известным @username")

for rec in recommendations:
    print(f"   {rec}")

print("\n" + "=" * 80)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 80)
