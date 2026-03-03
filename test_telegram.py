#!/usr/bin/env python3
"""Тест отправки Telegram уведомлений"""

import sys
from app import app, send_telegram_notification_sync

# Получаем username из аргументов командной строки
username = sys.argv[1] if len(sys.argv) > 1 else '@flowxz'
chat_id = sys.argv[2] if len(sys.argv) > 2 else None

with app.app_context():
    print("=" * 80)
    print("ТЕСТ: Отправка Telegram уведомлений")
    print("=" * 80)
    print(f"\n🎯 Получатель: {username}")
    if chat_id:
        print(f"🎯 chat_id: {chat_id}")
    print("")
    
    # Тест 1: Заявка подана
    print("\n1️⃣  Тест отправки ЗАЯВКА ПОДАНА уведомления...")
    sent, resolved_chat_id, error = send_telegram_notification_sync(username, 'submitted', chat_id)
    if sent:
        print(f"   ✅ Успешно отправлено!")
        print(f"   📝 Разрешенный chat_id: {resolved_chat_id}")
    else:
        print(f"   ❌ Ошибка: {error}")
    
    # Тест 2: Одобрено
    print("\n2️⃣  Тест отправки ОДОБРЕНО уведомления...")
    sent, resolved_chat_id, error = send_telegram_notification_sync(username, 'approved', resolved_chat_id or chat_id)
    if sent:
        print(f"   ✅ Успешно отправлено!")
        print(f"   📝 Разрешенный chat_id: {resolved_chat_id}")
    else:
        print(f"   ❌ Ошибка: {error}")
    
    # Тест 3: Отклонено
    print("\n3️⃣  Тест отправки ОТКЛОНЕНО уведомления...")
    sent, resolved_chat_id, error = send_telegram_notification_sync(username, 'rejected', resolved_chat_id or chat_id)
    if sent:
        print(f"   ✅ Успешно отправлено!")
        print(f"   📝 Разрешенный chat_id: {resolved_chat_id}")
    else:
        print(f"   ❌ Ошибка: {error}")
    
    print("\n" + "=" * 80)
    print("📋 РЕКОМЕНДАЦИИ:")
    print("=" * 80)
    print("1. Убедитесь что пользователь написал боту /start")
    print("2. Используйте: python test_telegram.py @username")
    print("3. Или с chat_id: python test_telegram.py @username 123456789")
    print("=" * 80)
