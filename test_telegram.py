#!/usr/bin/env python3
"""Тест отправки Telegram уведомлений"""

from app import app, send_telegram_notification_sync

with app.app_context():
    print("=" * 80)
    print("ТЕСТ: Отправка Telegram уведомлений")
    print("=" * 80)
    
    # Тест 1: Одобрено
    print("\n1️⃣  Тест отправки ОДОБРЕНО уведомления...")
    result = send_telegram_notification_sync('@flowxz', 'approved')
    print(f"   Результат: {'✅ Успешно' if result else '❌ Ошибка'}")
    
    # Тест 2: Отклонено
    print("\n2️⃣  Тест отправки ОТКЛОНЕНО уведомления...")
    result = send_telegram_notification_sync('@flowxz', 'rejected')
    print(f"   Результат: {'✅ Успешно' if result else '❌ Ошибка'}")
    
    print("\n" + "=" * 80)
    print("Если видишь ошибки - проверь:")
    print("1. Токен бота правильный")
    print("2. Юзернейм существует в Telegram")
    print("3. Бот может отправлять личные сообщения")
    print("=" * 80)
