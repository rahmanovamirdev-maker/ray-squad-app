from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
import os
import io
import string
import random
import logging
from logging.handlers import RotatingFileHandler
import smtplib
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from email.message import EmailMessage
from pyngrok import ngrok
import asyncio
import re
from collections import deque

try:
    from telegram import Bot
    from telegram.error import TelegramError
except Exception:
    Bot = None

    class TelegramError(Exception):
        pass

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

INSTANCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
APP_LOG_PATH = os.path.join(INSTANCE_DIR, 'app.log')
AUDIT_LOG_PATH = os.path.join(INSTANCE_DIR, 'audit.log')

ALLOWED_SCOUT_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def is_allowed_scout_photo(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_SCOUT_PHOTO_EXTENSIONS

def generate_strong_password(length=12):
    """Генерирует сложный пароль со спецсимволами, цифрами и буквами"""
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special_chars = "!@#$%^&*"
    
    # Гарантируем, что пароль содержит все типы символов
    password = [
        random.choice(uppercase),
        random.choice(lowercase),
        random.choice(digits),
        random.choice(special_chars)
    ]
    
    # Добавляем остальные символы случайным образом
    all_chars = uppercase + lowercase + digits + special_chars
    for _ in range(length - 4):
        password.append(random.choice(all_chars))
    
    # Перемешиваем пароль
    random.shuffle(password)
    return ''.join(password)

# ============= MAINTENANCE MODE =============
MAINTENANCE_MODE = False  # Установите False, чтобы открыть сайт
DEV_PASSWORD = "vrAynluktEww"  # Пароль для входа разработчика во время техработ
# ============================================

db = SQLAlchemy(app)

# Блокировка всех запросов в режиме обслуживания
@app.before_request
def check_maintenance():
    # Проверяем, есть ли у пользователя сессия разработчика
    allowed_endpoints = {'dev_login', 'dev_logout', 'static'}
    if MAINTENANCE_MODE and 'dev_session' not in session and request.endpoint not in allowed_endpoints:
        return '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Сайт временно закрыт</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Abhaya+Libre:wght@700;800&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-blue: #0066ff;
                    --dark-blue: #0047b3;
                    --accent-blue: #00bfff;
                    --black: #000000;
                    --dark-gray: #0a0e1a;
                    --light-gray: #8a92a6;
                    --white: #ffffff;
                }

                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                body {
                    font-family: 'Inter', sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: var(--black);
                    color: var(--white);
                    overflow: hidden;
                    position: relative;
                }

                body::before {
                    content: '';
                    position: fixed;
                    inset: 0;
                    background:
                        radial-gradient(circle at 20% 50%, rgba(0, 102, 255, 0.14) 0%, transparent 50%),
                        radial-gradient(circle at 80% 80%, rgba(0, 191, 255, 0.09) 0%, transparent 50%);
                    pointer-events: none;
                    z-index: 0;
                }

                body::after {
                    content: '';
                    position: fixed;
                    inset: 0;
                    background-image:
                        linear-gradient(rgba(0, 102, 255, 0.03) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(0, 102, 255, 0.03) 1px, transparent 1px);
                    background-size: 50px 50px;
                    opacity: 0.3;
                    pointer-events: none;
                    z-index: 0;
                }

                .container {
                    text-align: center;
                    width: min(94vw, 720px);
                    padding: 40px 36px;
                    background: rgba(10, 14, 26, 0.95);
                    border: 1px solid rgba(0, 102, 255, 0.2);
                    border-radius: 24px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
                    backdrop-filter: blur(30px);
                    position: relative;
                    z-index: 1;
                    animation: riseIn 0.55s ease-out;
                }

                @keyframes riseIn {
                    from {
                        opacity: 0;
                        transform: translateY(22px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .logo {
                    font-family: 'Abhaya Libre', serif;
                    font-size: 34px;
                    font-weight: 800;
                    letter-spacing: -1px;
                    margin-bottom: 18px;
                }

                .logo-accent {
                    background: linear-gradient(135deg, var(--primary-blue), var(--accent-blue));
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }

                h1 {
                    font-size: clamp(1.9rem, 4vw, 3rem);
                    margin-bottom: 14px;
                    letter-spacing: -0.02em;
                    line-height: 1.1;
                }

                p {
                    font-size: clamp(1rem, 2.1vw, 1.22rem);
                    color: var(--light-gray);
                    line-height: 1.55;
                    margin-bottom: 8px;
                }

                .status {
                    margin: 20px auto 0;
                    width: fit-content;
                    padding: 10px 18px;
                    border-radius: 50px;
                    border: 1px solid rgba(0, 102, 255, 0.32);
                    background: rgba(0, 102, 255, 0.15);
                    color: #8fd1ff;
                    font-weight: 600;
                    font-size: 0.95rem;
                }

                .dev-login-btn {
                    margin-top: 30px;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 10px;
                    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                    color: white;
                    font-weight: 600;
                    font-size: 0.95rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
                }

                .dev-login-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
                }

                .dev-login-modal {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.8);
                    z-index: 1000;
                    justify-content: center;
                    align-items: center;
                }

                .dev-login-modal.active {
                    display: flex;
                }

                .dev-login-form {
                    background: rgba(10, 14, 26, 0.98);
                    border: 1px solid rgba(0, 102, 255, 0.2);
                    border-radius: 18px;
                    padding: 32px;
                    max-width: 400px;
                    width: 90%;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
                }

                .dev-login-form h2 {
                    margin-bottom: 20px;
                    font-size: 1.5rem;
                }

                .dev-login-form input {
                    width: 100%;
                    padding: 12px 16px;
                    margin-bottom: 16px;
                    border: 1px solid rgba(0, 102, 255, 0.3);
                    border-radius: 8px;
                    background: rgba(0, 102, 255, 0.05);
                    color: white;
                    font-size: 1rem;
                    transition: all 0.3s;
                }

                .dev-login-form input:focus {
                    outline: none;
                    border-color: #0066ff;
                    background: rgba(0, 102, 255, 0.1);
                }

                .dev-login-form button {
                    width: 100%;
                    padding: 12px;
                    margin-bottom: 10px;
                    border: none;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s;
                }

                .dev-login-form .btn-submit {
                    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                    color: white;
                }

                .dev-login-form .btn-submit:hover {
                    transform: translateY(-2px);
                }

                .dev-login-form .btn-cancel {
                    background: #2d2d3d;
                    color: #e0e0e0;
                }

                .dev-login-form .btn-cancel:hover {
                    background: #3d3d4d;
                }

                .dev-login-form .error {
                    color: #ff4444;
                    margin-bottom: 12px;
                    font-size: 0.9rem;
                    display: none;
                }

                @media (max-width: 640px) {
                    .container {
                        padding: 28px 22px;
                        border-radius: 18px;
                    }

                    .logo {
                        font-size: 28px;
                        margin-bottom: 12px;
                    }

                    .status {
                        margin-top: 16px;
                        font-size: 0.88rem;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">LiamKing <span class="logo-accent">Agency</span></div>
                <h1>Сайт временно закрыт</h1>
                <p>Проводятся технические работы</p>
                <p>Приносим извинения за неудобства</p>
                <div class="status">Скоро снова онлайн</div>
                <button class="dev-login-btn" onclick="showDevLogin()">🔧 Вход разработчика</button>
            </div>

            <div class="dev-login-modal" id="devLoginModal">
                <div class="dev-login-form">
                    <h2>🔐 Вход разработчика</h2>
                    <div class="error" id="devLoginError"></div>
                    <form onsubmit="submitDevLogin(event)">
                        <input type="password" id="devPassword" placeholder="Введите пароль" required>
                        <button type="submit" class="btn-submit">Войти</button>
                        <button type="button" class="btn-cancel" onclick="hideDevLogin()">Закрыть</button>
                    </form>
                </div>
            </div>

            <script>
                function showDevLogin() {
                    document.getElementById('devLoginModal').classList.add('active');
                    document.getElementById('devPassword').focus();
                }

                function hideDevLogin() {
                    document.getElementById('devLoginModal').classList.remove('active');
                    document.getElementById('devPassword').value = '';
                    document.getElementById('devLoginError').style.display = 'none';
                }

                async function submitDevLogin(event) {
                    event.preventDefault();
                    const password = document.getElementById('devPassword').value;

                    try {
                        const response = await fetch('/dev-login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ password: password })
                        });

                        const data = await response.json();

                        if (data.success) {
                            window.location.href = '/';
                        } else {
                            const errorDiv = document.getElementById('devLoginError');
                            errorDiv.textContent = data.message || 'Неверный пароль';
                            errorDiv.style.display = 'block';
                            document.getElementById('devPassword').value = '';
                        }
                    } catch (error) {
                        console.error('Ошибка:', error);
                    }
                }

                // Закрыть модал при клике вне его
                document.getElementById('devLoginModal').addEventListener('click', function(e) {
                    if (e.target === this) {
                        hideDevLogin();
                    }
                });
            </script>
        </body>
        </html>
        ''', 503

# ============= TELEGRAM BOT CONFIGURATION =============
TELEGRAM_BOT_TOKEN = (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()
telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN) if (Bot and TELEGRAM_BOT_TOKEN) else None

# ============= GMAIL SMTP CONFIGURATION =============
SMTP_HOST = (os.environ.get('SMTP_HOST') or 'smtp.gmail.com').strip()
SMTP_PORT = int((os.environ.get('SMTP_PORT') or '587').strip())
SMTP_USER = (os.environ.get('SMTP_USER') or '').strip()
SMTP_PASSWORD = (os.environ.get('SMTP_PASSWORD') or '').strip()  # Gmail App Password
SMTP_FROM = (os.environ.get('SMTP_FROM') or SMTP_USER).strip()

# ============= DEV LOGIN ROUTE =============
@app.route('/dev-login', methods=['POST'])
def dev_login():
    data = request.get_json()
    password = data.get('password', '')
    
    if password == DEV_PASSWORD:
        session['dev_session'] = True
        return jsonify({'success': True, 'message': 'Добро пожаловать!'})
    else:
        return jsonify({'success': False, 'message': 'Неверный пароль'})

@app.route('/dev-logout', methods=['GET', 'POST'])
def dev_logout():
    session.pop('dev_session', None)
    return redirect(url_for('index'))
# ===========================================

async def send_telegram_notification(telegram_username, status):
    """
    Отправить уведомление в Telegram по username
    status: 'approved' или 'rejected'
    """
def normalize_telegram_username(raw_username):
    username = (raw_username or '').strip()
    if not username:
        return ''
    return username if username.startswith('@') else f"@{username}"


def is_numeric_chat_id(value):
    value_str = str(value or '').strip()
    return bool(re.fullmatch(r'-?\d+', value_str))


async def resolve_chat_id_by_username(telegram_username):
    normalized = normalize_telegram_username(telegram_username)
    if not normalized:
        return None

    expected = normalized.lstrip('@').lower()

    try:
        updates = await telegram_bot.get_updates(limit=100, timeout=0)
        for update in updates:
            message = update.message or update.edited_message
            if not message or not message.chat:
                continue
            if message.chat.type != 'private':
                continue

            candidates = []
            if message.chat.username:
                candidates.append(message.chat.username.lower())
            if message.from_user and message.from_user.username:
                candidates.append(message.from_user.username.lower())

            if expected in candidates:
                return str(message.chat.id)
    except Exception as e:
        logging.error(f"Ошибка при resolve_chat_id_by_username({normalized}): {e}")

    return None


async def send_telegram_notification(telegram_username, status, telegram_chat_id=None):
    """
    Возвращает tuple: (sent: bool, resolved_chat_id: str|None, error_message: str|None)
    """
    try:
        if not telegram_bot:
            logging.warning("Telegram notifications disabled: missing bot dependency or TELEGRAM_BOT_TOKEN")
            return False, None, 'Бот не настроен на сервере'

        if status == 'submitted':
            message = (
                "📝 <b>ЗАЯВКА ПОЛУЧЕНА!</b>\n\n"
                "Ваша заявка на вступление в команду успешно получена и находится на рассмотрении.\n\n"
                "Мы свяжемся с вами в ближайшее время! ⏳"
            )
        elif status == 'approved':
            message = (
                "✅ <b>ОТЛИЧНО!</b>\n\n"
                "Вашу заявку одобрили и с вами свяжутся в течение некоторого времени.\n\n"
                "Спасибо, что присоединяетесь к нашей команде! 🚀"
            )
        elif status == 'rejected':
            message = (
                "❌ <b>К СОЖАЛЕНИЮ</b>\n\n"
                "Вашу заявку отклонили. Вы не справились с заданием.\n\n"
                "Не расстраивайтесь — вы можете попробовать снова позже. 💪"
            )
        else:
            return False, None, 'Неизвестный статус уведомления'

        resolved_chat_id = None
        if is_numeric_chat_id(telegram_chat_id):
            resolved_chat_id = str(telegram_chat_id).strip()
        else:
            resolved_chat_id = await resolve_chat_id_by_username(telegram_username)

        if not resolved_chat_id:
            return False, None, 'Пользователь не найден в диалогах бота. Нужно нажать /start боту.'

        await telegram_bot.send_message(
            chat_id=resolved_chat_id,
            text=message,
            parse_mode='HTML'
        )

        logging.info(f"✅ Telegram уведомление отправлено chat_id={resolved_chat_id} (status={status})")
        return True, resolved_chat_id, None

    except TelegramError as e:
        logging.error(f"❌ Ошибка Telegram для {telegram_username}: {e}")
        return False, None, str(e)
    except Exception as e:
        logging.error(f"❌ Неожиданная ошибка при отправке в Telegram: {e}")
        return False, None, str(e)


def send_telegram_notification_sync(telegram_username, status, telegram_chat_id=None):
    """Синхронная обертка для отправки уведомлений"""
    try:
        try:
            return asyncio.run(send_telegram_notification(telegram_username, status, telegram_chat_id))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(send_telegram_notification(telegram_username, status, telegram_chat_id))
            loop.close()
            return result
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления: {e}")
        return False, None, str(e)


def is_valid_email(email_value):
    email_value = (email_value or '').strip()
    if not email_value:
        return False
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email_value))


def send_email_notification(email_to, status, full_name=''):
    """Отправляет email-уведомление о статусе заявки. Возвращает (sent: bool, error: str|None)."""
    if not (SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
        return False, 'SMTP не настроен (SMTP_USER/SMTP_PASSWORD/SMTP_FROM)'

    recipient = (email_to or '').strip()
    if not is_valid_email(recipient):
        return False, 'Некорректный email получателя'

    person_name = (full_name or 'кандидат').strip()
    if status == 'approved':
        subject = 'Ваша заявка одобрена - LiamKing Agency'
        body = (
            f"Здравствуйте, {person_name}!\n\n"
            "Ваша заявка одобрена. С вами свяжутся в ближайшее время.\n\n"
            "С уважением,\n"
            "LiamKing Agency"
        )
    elif status == 'rejected':
        subject = 'Результат по заявке - LiamKing Agency'
        body = (
            f"Здравствуйте, {person_name}!\n\n"
            "К сожалению, ваша заявка на текущий момент отклонена.\n"
            "Вы можете попробовать подать заявку позже.\n\n"
            "С уважением,\n"
            "LiamKing Agency"
        )
    else:
        return False, 'Неизвестный статус email-уведомления'

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = SMTP_FROM
        msg['To'] = recipient
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logging.info(f"✅ Email уведомление отправлено на {recipient} (status={status})")
        return True, None
    except Exception as e:
        logging.error(f"❌ Ошибка email-уведомления для {recipient}: {e}")
        return False, str(e)

# ===================================================

# Отключение кэширования для всех API ответов
@app.after_request
def disable_caching(response):
    """Отключить кэширование для API ответов"""
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Функция для получения московского времени (UTC+3)
def moscow_now():
    return datetime.now(timezone(timedelta(hours=3)))

# Модель для хранения анкет
class Applicant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.String(50))
    english_level = db.Column(db.String(500))
    cpu_model = db.Column(db.String(200))
    gpu_model = db.Column(db.String(200))
    internet_speed = db.Column(db.String(100))
    work_experience = db.Column(db.String(500))
    interview_time = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=False)
    telegram = db.Column(db.String(100))
    date_added = db.Column(db.DateTime, default=moscow_now)
    owner_username = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    team = db.Column(db.String(50))  # Команда (Team 1 - Team 8)
    is_deleted = db.Column(db.Boolean, default=False)  # Мягкое удаление

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth,
            'english_level': self.english_level,
            'cpu_model': self.cpu_model,
            'gpu_model': self.gpu_model,
            'internet_speed': self.internet_speed,
            'work_experience': self.work_experience,
            'interview_time': self.interview_time,
            'phone': self.phone,
            'telegram': self.telegram,
            'date_added': self.date_added.strftime('%d.%m.%Y %H:%M'),
            'owner_username': self.owner_username,
            'status': self.status,
            'team': self.team,
            'is_deleted': self.is_deleted
        }

# Модель пользователей
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(120))
    bio = db.Column(db.String(500))
    avatar_url = db.Column(db.String(500))
    prefix = db.Column(db.String(50))  # Префикс/звание пользователя (Developer, Admin, etc.)
    is_admin = db.Column(db.Boolean, default=False)
    is_owner = db.Column(db.Boolean, default=False)  # Владелец - полный доступ
    can_submit = db.Column(db.Boolean, default=True)  # Может ли отправлять ответы
    crypto_wallet = db.Column(db.String(200))  # Крипто кошелек
    earned_amount = db.Column(db.Float, default=0.0)  # Заработанная сумма
    created_at = db.Column(db.DateTime, default=moscow_now)
    last_login_at = db.Column(db.DateTime)
    team = db.Column(db.String(50))  # Команда (Team 1 - Team 8)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'prefix': self.prefix,
            'is_admin': self.is_admin,
            'is_owner': self.is_owner,
            'team': self.team,
            'created_at': self.created_at.strftime('%d.%m.%Y %H:%M') if self.created_at else None,
            'last_login_at': self.last_login_at.strftime('%d.%m.%Y %H:%M') if self.last_login_at else None
        }

# Модель для вопросов отбора


# Модель для слотов собеседований
class InterviewSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    is_open = db.Column(db.Boolean, default=True)
    slot_type = db.Column(db.String(50), default='operator')  # 'operator' или 'model'
    created_at = db.Column(db.DateTime, default=moscow_now)

    def to_dict(self):
        start_str = self.start_time.strftime('%d.%m.%Y %H:%M')
        end_str = self.end_time.strftime('%d.%m.%Y %H:%M') if self.end_time else None
        return {
            'id': self.id,
            'start_time': start_str,
            'end_time': end_str,
            'is_open': self.is_open,
            'slot_type': self.slot_type
        }

# Модель для анкет моделей/операторов
class ModelOperatorApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    age = db.Column(db.String(50))
    residence = db.Column(db.String(50))  # "одна" или "не одна"
    has_dual_devices = db.Column(db.String(50))  # "да" или "нет" - 2 мобильных или комп+телефон
    device_model = db.Column(db.String(200))
    work_hours = db.Column(db.String(200))  # Сколько часов и дней в неделю
    has_headphones = db.Column(db.String(50))  # "да" или "нет"
    telegram = db.Column(db.String(100))
    interview_time = db.Column(db.String(100))  # Время собеседования модели
    photos = db.Column(db.Text)  # Сохраняем пути к фото через запятую или JSON
    owner_username = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    date_added = db.Column(db.DateTime, default=moscow_now)
    team = db.Column(db.String(50))  # Команда (Team 1 - Team 8)
    is_deleted = db.Column(db.Boolean, default=False)  # Мягкое удаление

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'city': self.city,
            'phone': self.phone,
            'age': self.age,
            'residence': self.residence,
            'has_dual_devices': self.has_dual_devices,
            'device_model': self.device_model,
            'work_hours': self.work_hours,
            'has_headphones': self.has_headphones,
            'telegram': self.telegram,
            'interview_time': self.interview_time,
            'photos': self.photos,
            'owner_username': self.owner_username,
            'status': self.status,
            'date_added': self.date_added.strftime('%d.%m.%Y %H:%M'),
            'team': self.team,
            'is_deleted': self.is_deleted
        }

# Модель для анкет Чаттеров
class ChatApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.String(50), nullable=False)
    geo = db.Column(db.String(100), nullable=False)  # Откуда документы
    experience = db.Column(db.String(500))  # Опыт в адалте
    offer_number = db.Column(db.String(50), nullable=False)  # Номер оффера (1, 2, 3)
    phone = db.Column(db.String(20), nullable=False)
    telegram = db.Column(db.String(100))
    owner_username = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    date_added = db.Column(db.DateTime, default=moscow_now)
    team = db.Column(db.String(50))  # Команда (Team 1 - Team 8)
    is_deleted = db.Column(db.Boolean, default=False)  # Мягкое удаление

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'age': self.age,
            'geo': self.geo,
            'experience': self.experience,
            'offer_number': self.offer_number,
            'phone': self.phone,
            'telegram': self.telegram,
            'owner_username': self.owner_username,
            'status': self.status,
            'date_added': self.date_added.strftime('%d.%m.%Y %H:%M'),
            'team': self.team,
            'is_deleted': self.is_deleted
        }


class ScoutJoinApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.String(30), nullable=False)
    persuasion_text = db.Column(db.Text, nullable=True)  # Оставляем для старых записей
    city = db.Column(db.String(100), nullable=True)  # Новое поле для стримерш
    streaming_experience = db.Column(db.String(50), nullable=True)  # Новое поле для стримерш
    motivation = db.Column(db.Text, nullable=True)  # Новое поле для стримерш
    email = db.Column(db.String(150), nullable=True)
    telegram_username = db.Column(db.String(120), nullable=False)
    telegram_chat_id = db.Column(db.String(50), nullable=True)
    work_time = db.Column(db.String(200), nullable=False)
    can_stream_change = db.Column(db.String(10), nullable=True)  # Может ли кто-то поменять стриму: yes/no
    device_model = db.Column(db.String(200), nullable=True)  # Модель устройства
    work_hours_per_week = db.Column(db.String(200), nullable=True)  # Часы и дни в неделю
    photo_url = db.Column(db.String(500), nullable=True)  # Путь на фото
    date_added = db.Column(db.DateTime, default=moscow_now)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by = db.Column(db.String(120), nullable=True)
    rejected_by = db.Column(db.String(120), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    team = db.Column(db.String(50), nullable=True)  # Команда (Team 1 - Team 8)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'age': self.age,
            'persuasion_text': self.persuasion_text,
            'city': self.city,
            'streaming_experience': self.streaming_experience,
            'motivation': self.motivation,
            'email': self.email,
            'telegram_username': self.telegram_username,
            'telegram_chat_id': self.telegram_chat_id,
            'work_time': self.work_time,
            'can_stream_change': self.can_stream_change,
            'device_model': self.device_model,
            'work_hours_per_week': self.work_hours_per_week,
            'photo_url': self.photo_url,
            'date_added': self.date_added.strftime('%d.%m.%Y %H:%M') if self.date_added else None,
            'status': self.status or 'pending',
            'approved_by': self.approved_by,
            'rejected_by': self.rejected_by,
            'reviewed_at': self.reviewed_at.strftime('%d.%m.%Y %H:%M') if self.reviewed_at else None
        }

# Модель для истории синхронизации статусов с внешним API


# Создание таблиц
with app.app_context():
    db.create_all()
    # If owner_username column doesn't exist in the table (older DB), try to add it
    try:
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        if 'applicant' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('applicant')]
            if 'owner_username' not in cols:
                # SQLite supports simple ALTER TABLE ADD COLUMN
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN owner_username VARCHAR(100)"))
                db.session.commit()
            if 'interview_time' not in cols:
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN interview_time VARCHAR(100)"))
                db.session.commit()
        if 'user' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('user')]
            if 'display_name' not in cols:
                print("[MIGRATION] Добавляю столбец display_name в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN display_name VARCHAR(120)"))
                db.session.commit()
                print("[MIGRATION] Столбец display_name добавлен успешно")
            if 'bio' not in cols:
                print("[MIGRATION] Добавляю столбец bio в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN bio VARCHAR(500)"))
                db.session.commit()
                print("[MIGRATION] Столбец bio добавлен успешно")
            if 'avatar_url' not in cols:
                print("[MIGRATION] Добавляю столбец avatar_url в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN avatar_url VARCHAR(500)"))
                db.session.commit()
                print("[MIGRATION] Столбец avatar_url добавлен успешно")
            if 'last_login_at' not in cols:
                print("[MIGRATION] Добавляю столбец last_login_at в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN last_login_at DATETIME"))
                db.session.commit()
                print("[MIGRATION] Столбец last_login_at добавлен успешно")
            if 'is_guest' not in cols:
                db.session.execute(text("ALTER TABLE user ADD COLUMN is_guest BOOLEAN DEFAULT 0"))
                db.session.commit()
            if 'is_owner' not in cols:
                print("[MIGRATION] Добавляю столбец is_owner в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN is_owner BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("[MIGRATION] Столбец is_owner добавлен успешно")
            if 'can_submit' not in cols:
                print("[MIGRATION] Добавляю столбец can_submit в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN can_submit BOOLEAN DEFAULT 1"))
                db.session.commit()
                print("[MIGRATION] Столбец can_submit добавлен успешно")
            if 'team' not in cols:
                print("[MIGRATION] Добавляю столбец team в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN team VARCHAR(50)"))
                db.session.commit()
                print("[MIGRATION] Столбец team добавлен успешно")
        if 'applicant' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('applicant')]
            if 'team' not in cols:
                print("[MIGRATION] Добавляю столбец team в таблицу applicant...")
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN team VARCHAR(50)"))
                db.session.commit()
                print("[MIGRATION] Столбец team добавлен успешно")
            if 'is_deleted' not in cols:
                print("[MIGRATION] Добавляю столбец is_deleted в таблицу applicant...")
                db.session.execute(text("ALTER TABLE applicant ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("[MIGRATION] Столбец is_deleted добавлен успешно")
        if 'model_operator_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('model_operator_application')]
            if 'team' not in cols:
                print("[MIGRATION] Добавляю столбец team в таблицу model_operator_application...")
                db.session.execute(text("ALTER TABLE model_operator_application ADD COLUMN team VARCHAR(50)"))
                db.session.commit()
                print("[MIGRATION] Столбец team добавлен успешно")
        if 'scout_join_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('scout_join_application')]
            if 'telegram_chat_id' not in cols:
                print("[MIGRATION] Добавляю столбец telegram_chat_id в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN telegram_chat_id VARCHAR(50)"))
                db.session.commit()
            if 'can_stream_change' not in cols:
                print("[MIGRATION] Добавляю столбец can_stream_change в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN can_stream_change VARCHAR(10)"))
                db.session.commit()
            if 'device_model' not in cols:
                print("[MIGRATION] Добавляю столбец device_model в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN device_model VARCHAR(200)"))
                db.session.commit()
            if 'work_hours_per_week' not in cols:
                print("[MIGRATION] Добавляю столбец work_hours_per_week в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN work_hours_per_week VARCHAR(200)"))
                db.session.commit()
            if 'photo_url' not in cols:
                print("[MIGRATION] Добавляю столбец photo_url в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN photo_url VARCHAR(500)"))
                db.session.commit()
            if 'email' not in cols:
                print("[MIGRATION] Добавляю столбец email в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN email VARCHAR(150)"))
                db.session.commit()
                print("[MIGRATION] Столбец telegram_chat_id добавлен успешно")
            if 'city' not in cols:
                print("[MIGRATION] Добавляю столбец city в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN city VARCHAR(100)"))
                db.session.commit()
            if 'streaming_experience' not in cols:
                print("[MIGRATION] Добавляю столбец streaming_experience в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN streaming_experience VARCHAR(50)"))
                db.session.commit()
            if 'motivation' not in cols:
                print("[MIGRATION] Добавляю столбец motivation в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN motivation TEXT"))
                db.session.commit()
        if 'guest_answer' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('guest_answer')]
            if 'user_id' not in cols:
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN user_id INTEGER"))
                db.session.commit()
            if 'guest_tg' not in cols:
                print("[MIGRATION] Добавляю столбец guest_tg в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_tg VARCHAR(100)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_tg добавлен успешно")
            if 'guest_phone' not in cols:
                # Этот столбец депрецирован, но добавляем за совместимость
                print("[MIGRATION] Добавляю столбец guest_phone в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_phone VARCHAR(20)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_phone добавлен успешно")
            if 'guest_age' not in cols:
                print("[MIGRATION] Добавляю столбец guest_age в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_age VARCHAR(10)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_age добавлен успешно")
            if 'guest_adult_exp' not in cols:
                print("[MIGRATION] Добавляю столбец guest_adult_exp в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_adult_exp VARCHAR(500)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_adult_exp добавлен успешно")
            if 'guest_work_hours' not in cols:
                print("[MIGRATION] Добавляю столбец guest_work_hours в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN guest_work_hours VARCHAR(200)"))
                db.session.commit()
                print("[MIGRATION] Столбец guest_work_hours добавлен успешно")
            if 'approved' not in cols:
                print("[MIGRATION] Добавляю столбец approved в таблицу guest_answer...")
                db.session.execute(text("ALTER TABLE guest_answer ADD COLUMN approved BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("[MIGRATION] Столбец approved добавлен успешно")
        if 'interview_slot' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('interview_slot')]
            if 'is_open' not in cols:
                print("[MIGRATION] Добавляю столбец is_open в таблицу interview_slot...")
                db.session.execute(text("ALTER TABLE interview_slot ADD COLUMN is_open BOOLEAN DEFAULT 1"))
                db.session.commit()
                print("[MIGRATION] Столбец is_open добавлен успешно")
            if 'slot_type' not in cols:
                print("[MIGRATION] Добавляю столбец slot_type в таблицу interview_slot...")
                db.session.execute(text("ALTER TABLE interview_slot ADD COLUMN slot_type VARCHAR(50) DEFAULT 'operator'"))
                db.session.commit()
                print("[MIGRATION] Столбец slot_type добавлен успешно")
        # Добавление interview_time для модели
        if 'model_operator_application' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('model_operator_application')]
            if 'interview_time' not in cols:
                print("[MIGRATION] Добавляю столбец interview_time в таблицу model_operator_application...")
                db.session.execute(text("ALTER TABLE model_operator_application ADD COLUMN interview_time VARCHAR(100)"))
                db.session.commit()
                print("[MIGRATION] Столбец interview_time добавлен успешно")
        # Таблица Message должна быть создана автоматически через db.create_all()
        if 'message' not in insp.get_table_names():
            print("[INFO] Таблица Message будет создана при следующей миграции")
        else:
            # Проверяем и мигрируем структуру таблицы message
            message_cols = [c['name'] for c in insp.get_columns('message')]
            if 'guest_user_id' not in message_cols:
                print("[MIGRATION] Пересоздаю таблицу message с новой схемой...")
                # Сохраняем старые данные
                db.session.execute(text("""
                    CREATE TABLE message_backup AS SELECT * FROM message
                """))
                # Удаляем старую таблицу
                db.session.execute(text("DROP TABLE message"))
                # Создаём новую таблицу с правильной схемой
                db.session.execute(text("""
                    CREATE TABLE message (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        guest_user_id INTEGER NOT NULL,
                        sender_id INTEGER NOT NULL,
                        sender_name VARCHAR(100),
                        message_text VARCHAR(2000) NOT NULL,
                        created_at DATETIME,
                        answer_id INTEGER,
                        FOREIGN KEY(guest_user_id) REFERENCES user (id),
                        FOREIGN KEY(sender_id) REFERENCES user (id),
                        FOREIGN KEY(answer_id) REFERENCES guest_answer (id)
                    )
                """))
                # Копируем старые данные, получая guest_user_id из answer_id
                db.session.execute(text("""
                    INSERT INTO message (id, guest_user_id, sender_id, sender_name, message_text, created_at, answer_id)
                    SELECT m.id, 
                           COALESCE(ga.user_id, m.sender_id) as guest_user_id,
                           m.sender_id, 
                           m.sender_name, 
                           m.message_text, 
                           m.created_at, 
                           m.answer_id
                    FROM message_backup m
                    LEFT JOIN guest_answer ga ON m.answer_id = ga.id
                """))
                # Удаляем бэкап
                db.session.execute(text("DROP TABLE message_backup"))
                db.session.commit()
                print("[MIGRATION] Таблица message успешно обновлена")
    except Exception as e:
        # If anything fails, continue — application can still run, but admin should be informed
        print(f"[MIGRATION ERROR] {str(e)}")
        pass

    # Ensure admin user exists
    try:
        # users table is created by db.create_all()
        admin = User.query.filter_by(username='FLOWXZ').first()
        if not admin:
            admin = User(
                username='FLOWXZ',
                password_hash=generate_password_hash('qwertyuiopasd'),
                is_admin=True,
                is_owner=True,
                prefix='Developer'
            )
            db.session.add(admin)
            db.session.commit()
            print("[INFO] Владелец FLOWXZ создан")
        else:
            updated = False
            if not admin.is_owner:
                # Устанавливаем существующему админу статус владельца
                admin.is_owner = True
                admin.is_admin = True
                updated = True
                print("[INFO] FLOWXZ установлен как Владелец")
            if (admin.prefix or '').strip().lower() != 'developer':
                admin.prefix = 'Developer'
                updated = True
                print("[INFO] FLOWXZ установлен префикс Developer")
            if updated:
                db.session.commit()
    except Exception as e:
        print(f"[ADMIN USER ERROR] {str(e)}")
        pass

# Логирование
logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')


def configure_logging():
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )

    app_handler = RotatingFileHandler(
        APP_LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    app_handler.setFormatter(formatter)

    audit_handler = RotatingFileHandler(
        AUDIT_LOG_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    audit_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    existing_handler_types = {type(h) for h in root_logger.handlers}
    if RotatingFileHandler not in existing_handler_types:
        root_logger.addHandler(app_handler)
    if logging.StreamHandler not in existing_handler_types:
        root_logger.addHandler(stream_handler)

    logger.setLevel(logging.INFO)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    if not audit_logger.handlers:
        audit_logger.addHandler(audit_handler)


def _truncate_value(value, limit=200):
    value_str = str(value)
    if len(value_str) <= limit:
        return value_str
    return f"{value_str[:limit]}..."


def _safe_request_payload_preview():
    sensitive_keys = {
        'password',
        'password_hash',
        'new_password',
        'secret',
        'token',
        'smtp_password'
    }

    payload = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}
        if isinstance(data, dict):
            for key, value in data.items():
                key_str = str(key)
                if key_str.lower() in sensitive_keys:
                    payload[key_str] = '***'
                else:
                    payload[key_str] = _truncate_value(value)
    elif request.form:
        for key, value in request.form.items():
            key_str = str(key)
            if key_str.lower() in sensitive_keys:
                payload[key_str] = '***'
            else:
                payload[key_str] = _truncate_value(value)

    if request.files:
        payload['files'] = list(request.files.keys())

    return payload


def _resolve_action_name():
    endpoint = (request.endpoint or '').strip()
    if endpoint:
        return endpoint
    return f"{request.method.lower()}_{request.path.strip('/').replace('/', '_') or 'root'}"


def _safe_log_text(value):
    return _truncate_value(str(value or '').replace('"', "'"), limit=180)


def _resolve_interaction_target(payload_preview):
    view_args = request.view_args or {}
    for key, value in view_args.items():
        if key.endswith('_id'):
            entity = key.replace('_id', '')
            return f"{entity}:{value}"

    interesting_payload_keys = [
        'user_id',
        'owner_username',
        'username',
        'telegram',
        'telegram_username',
        'full_name',
        'team',
        'status',
        'offer_number'
    ]
    if isinstance(payload_preview, dict):
        for key in interesting_payload_keys:
            if key in payload_preview:
                return f"{key}:{payload_preview.get(key)}"

    return '-'


def _resolve_related_user(payload_preview):
    if not isinstance(payload_preview, dict):
        return '-'

    for key in ('username', 'owner_username', 'telegram_username', 'telegram'):
        if key in payload_preview and payload_preview.get(key):
            return str(payload_preview.get(key))
    return '-'


def _resolve_event_description(action_name, method, path, target, related_user, status_code):
    action_raw = (action_name or '').lower()
    path_raw = (path or '').lower()
    method_raw = (method or '').upper()

    if 'login' in action_raw or '/login' in path_raw:
        return 'Вход в систему'
    if 'logout' in action_raw or '/logout' in path_raw:
        return 'Выход из системы'
    if 'reset_user_password' in action_raw or '/api/reset-password/' in path_raw:
        return f'Сброс пароля пользователя {related_user if related_user != "-" else target}'
    if 'admin_create_user' in action_raw or '/admin/create-user' in path_raw:
        return f'Создание пользователя {related_user if related_user != "-" else ""}'.strip()
    if 'admin_delete_user' in action_raw or '/admin/delete-user/' in path_raw:
        return f'Удаление пользователя {target}'
    if 'update_user_team' in action_raw or '/api/update-team/' in path_raw:
        return f'Изменение команды пользователя {target}'
    if 'update_applicant_status' in action_raw:
        return f'Изменение статуса анкеты {target}'
    if 'update_model_operator_status' in action_raw:
        return f'Изменение статуса анкеты модели {target}'
    if 'update_chatter_status' in action_raw:
        return f'Изменение статуса анкеты чаттера {target}'
    if 'delete_applicant' in action_raw:
        return f'Удаление анкеты {target}'
    if 'delete_model' in action_raw:
        return f'Удаление анкеты модели {target}'
    if 'delete_chatter' in action_raw:
        return f'Удаление анкеты чаттера {target}'
    if 'admin_approve_scout' in action_raw:
        return f'Одобрение заявки стримерши {target}'
    if 'admin_reject_scout' in action_raw:
        return f'Отклонение заявки стримерши {target}'
    if 'add_applicant' in action_raw:
        return 'Создание анкеты оператора'
    if 'add_model_operator' in action_raw:
        return 'Создание анкеты модели/оператора'
    if 'add_chatter' in action_raw:
        return 'Создание анкеты чаттера'
    if 'public_scout_application' in action_raw:
        return 'Подача публичной заявки стримерши'
    if method_raw == 'GET':
        return f'Просмотр данных ({status_code})'
    if method_raw == 'POST':
        return f'Создание/действие ({status_code})'
    if method_raw in {'PUT', 'PATCH'}:
        return f'Обновление данных ({status_code})'
    if method_raw == 'DELETE':
        return f'Удаление данных ({status_code})'

    return f'Системное действие ({status_code})'


def is_developer_user(user):
    return bool(user and (user.prefix or '').strip().lower() == 'developer')


def is_moderator_user(user):
    return bool(user and (user.prefix or '').strip().lower() == 'moderator')


def can_access_admin_panel(user):
    return bool(user and (user.is_admin or is_moderator_user(user)))


def has_full_admin_access(user):
    return bool(user and user.is_admin and not is_moderator_user(user))


def get_user_applications(owner_username):
    """Возвращает полный список анкет пользователя по всем типам."""
    username = (owner_username or '').strip()
    if not username:
        return []

    items = []

    operators = Applicant.query.filter_by(owner_username=username).all()
    for row in operators:
        items.append({
            'kind': 'operator',
            'kind_label': 'Оператор',
            'id': row.id,
            'full_name': row.full_name,
            'status': row.status or 'pending',
            'team': row.team,
            'contact': row.telegram or row.phone or '-',
            'date_added': row.date_added,
            'is_deleted': bool(row.is_deleted)
        })

    models = ModelOperatorApplication.query.filter_by(owner_username=username).all()
    for row in models:
        items.append({
            'kind': 'model',
            'kind_label': 'Модель/Оператор',
            'id': row.id,
            'full_name': row.full_name,
            'status': row.status or 'pending',
            'team': row.team,
            'contact': row.telegram or row.phone or '-',
            'date_added': row.date_added,
            'is_deleted': bool(row.is_deleted)
        })

    chatters = ChatApplication.query.filter_by(owner_username=username).all()
    for row in chatters:
        items.append({
            'kind': 'chatter',
            'kind_label': 'Чаттер',
            'id': row.id,
            'full_name': row.full_name,
            'status': row.status or 'pending',
            'team': row.team,
            'contact': row.telegram or row.phone or '-',
            'date_added': row.date_added,
            'is_deleted': bool(row.is_deleted)
        })

    items.sort(key=lambda x: x.get('date_added') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


@app.before_request
def start_audit_context():
    g.request_started_at = datetime.now(timezone.utc)
    g.skip_audit_logging = request.path.startswith('/static/')
    g.actor_id = session.get('user_id')
    g.actor_username = 'anonymous'

    if g.actor_id:
        user = User.query.get(g.actor_id)
        if user:
            g.actor_username = user.username


@app.after_request
def audit_request(response):
    if getattr(g, 'skip_audit_logging', False):
        return response

    started_at = getattr(g, 'request_started_at', None)
    duration_ms = 0
    if started_at:
        duration_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

    payload_preview = {}
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        payload_preview = _safe_request_payload_preview()

    action_name = _resolve_action_name()
    target = _resolve_interaction_target(payload_preview)
    related_user = _resolve_related_user(payload_preview)
    event_description = _resolve_event_description(
        action_name,
        request.method,
        request.path,
        target,
        related_user,
        response.status_code
    )

    audit_logger.info(
        (
            'REQUEST actor=%s user_id=%s action=%s method=%s path=%s endpoint=%s status=%s '
            'target=%s related_user=%s event="%s" ip=%s duration_ms=%s ua="%s" payload=%s'
        ),
        getattr(g, 'actor_username', 'anonymous'),
        getattr(g, 'actor_id', None),
        action_name,
        request.method,
        request.path,
        request.endpoint,
        response.status_code,
        target,
        related_user,
        _safe_log_text(event_description),
        request.headers.get('X-Forwarded-For', request.remote_addr),
        duration_ms,
        _truncate_value(request.user_agent.string, limit=180),
        payload_preview
    )

    return response


@app.teardown_request
def log_unhandled_request_error(error):
    if not error:
        return

    logger.exception(
        'UNHANDLED_ERROR actor=%s user_id=%s method=%s path=%s ip=%s',
        getattr(g, 'actor_username', 'anonymous'),
        getattr(g, 'actor_id', None),
        request.method,
        request.path,
        request.headers.get('X-Forwarded-For', request.remote_addr)
    )


configure_logging()

# ==================== ФУНКЦИИ ДЛЯ СИНХРОНИЗАЦИИ СТАТУСОВ ====================



# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    """Главная landing страница"""
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    """Панель управления анкетами"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    page = request.args.get('page', 1, type=int)
    if user and user.is_admin:
        # Показываем только не удаленные анкеты
        applicants = Applicant.query.filter_by(is_deleted=False).order_by(Applicant.date_added.desc()).paginate(page=page, per_page=10)
    else:
        # Пользователь видит только свои не удаленные анкеты
        applicants = Applicant.query.filter_by(owner_username=user.username, is_deleted=False).order_by(Applicant.date_added.desc()).paginate(page=page, per_page=10)
    return render_template('index.html', applicants=applicants, current_user=user)

@app.route('/manual')
def manual():
    """Страница с мануалом"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('manual.html', current_user=user)

# Функция для проверки занятых слотов между выбранным временем
def check_conflicting_closed_slots(slot_start, slot_end):
    """
    Проверяет, есть ли закрытые (занятые) слоты между start и end временем.
    Возвращает список конфликтующих слотов или пустой список.
    """
    conflicting_slots = []
    all_slots = InterviewSlot.query.all()
    
    for slot in all_slots:
        # Пропускаем открытые слоты
        if slot.is_open:
            continue
            
        slot_actual_end = slot.end_time or slot.start_time
        
        # Проверяем пересечение между нашим временем и закрытым слотом
        # Пересечение есть если: start < closed_end AND end > closed_start
        if slot_start < slot_actual_end and slot_end > slot.start_time:
            conflicting_slots.append({
                'start': slot.start_time.strftime('%d.%m.%Y %H:%M'),
                'end': slot_actual_end.strftime('%d.%m.%Y %H:%M')
            })
    
    return conflicting_slots

# Функция для проверки дубликатов анкет
def check_duplicate_applicants(phone, telegram, full_name):
    """
    Проверяет наличие дубликатов по телефону, телеграму или имени.
    Возвращает список найденных похожих анкет с информацией о совпадении.
    """
    duplicates = []
    
    # Проверка по телефону (точное совпадение) только среди не удаленных анкет
    if phone:
        phone_clean = phone.strip()
        existing_by_phone = Applicant.query.filter_by(phone=phone_clean, is_deleted=False).all()
        for app in existing_by_phone:
            duplicates.append({
                'id': app.id,
                'full_name': app.full_name,
                'phone': app.phone,
                'telegram': app.telegram,
                'date_added': app.date_added.strftime('%d.%m.%Y %H:%M'),
                'match_type': 'телефон',
                'status': app.status
            })
    
    # Проверка по телеграму (точное совпадение, игнорируя @) только среди не удаленных
    if telegram:
        telegram_clean = telegram.strip().lstrip('@').lower()
        if telegram_clean:
            all_applicants = Applicant.query.filter_by(is_deleted=False).all()
            for app in all_applicants:
                if app.telegram:
                    app_tg_clean = app.telegram.strip().lstrip('@').lower()
                    if app_tg_clean == telegram_clean:
                        # Проверяем, не добавили ли уже эту анкету (по телефону)
                        if not any(d['id'] == app.id for d in duplicates):
                            duplicates.append({
                                'id': app.id,
                                'full_name': app.full_name,
                                'phone': app.phone,
                                'telegram': app.telegram,
                                'date_added': app.date_added.strftime('%d.%m.%Y %H:%M'),
                                'match_type': 'телеграм',
                                'status': app.status
                            })
    
    # Проверка по полному имени (точное совпадение) только среди не удаленных
    if full_name:
        name_clean = full_name.strip().lower()
        all_applicants = Applicant.query.filter_by(is_deleted=False).all()
        for app in all_applicants:
            if app.full_name and app.full_name.strip().lower() == name_clean:
                # Проверяем, не добавили ли уже эту анкету
                if not any(d['id'] == app.id for d in duplicates):
                    duplicates.append({
                        'id': app.id,
                        'full_name': app.full_name,
                        'phone': app.phone,
                        'telegram': app.telegram,
                        'date_added': app.date_added.strftime('%d.%m.%Y %H:%M'),
                        'match_type': 'имя',
                        'status': app.status
                    })
    
    return duplicates

@app.route('/api/add-applicant', methods=['POST'])
def add_applicant():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        data = request.json

        slot_id = data.get('interview_slot_id')
        interview_time_value = (data.get('interview_time', '') or '').strip()

        open_slots_count = InterviewSlot.query.filter_by(is_open=True).count()
        if open_slots_count == 0:
            return jsonify({'success': False, 'message': 'Сейчас нет открытых слотов для собеседования'}), 400

        if not slot_id and not interview_time_value:
            return jsonify({'success': False, 'message': 'Укажите время собеседования'}), 400

        slot_start = None
        slot_end = None
        warning_message = None

        if interview_time_value and not slot_id:
            try:
                requested_dt = datetime.strptime(interview_time_value, '%d.%m.%Y %H:%M')
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Неверный формат времени. Используйте ДД.ММ.ГГГГ ЧЧ:ММ'
                }), 400

            open_slots = InterviewSlot.query.filter_by(is_open=True).all()
            slot_match = False
            matched_slot = None
            for slot in open_slots:
                start = slot.start_time
                end = slot.end_time or slot.start_time
                if start <= requested_dt <= end:
                    slot_match = True
                    matched_slot = slot
                    slot_start = start
                    slot_end = end
                    break

            if not slot_match:
                return jsonify({
                    'success': False,
                    'message': 'Нет свободных слотов на эту дату'
                }), 400
            
            # Проверяем конфликты только если слот имеет диапазон
            if slot_start and slot_end:
                conflicting = check_conflicting_closed_slots(slot_start, slot_end)
                if conflicting:
                    conflict_times = ', '.join([f"{c['start']} - {c['end']}" for c in conflicting])
                    warning_message = f"⚠️ Внимание: между выбранным временем обнаружены занятые слоты: {conflict_times}"

        if slot_id:
            slot = InterviewSlot.query.get(slot_id)
            if not slot or not slot.is_open:
                return jsonify({'success': False, 'message': 'Выбранный слот уже закрыт'}), 400
            
            slot_start = slot.start_time
            slot_end = slot.end_time or slot.start_time
            
            start_str = slot.start_time.strftime('%d.%m.%Y %H:%M')
            if slot.end_time:
                end_str = slot.end_time.strftime('%d.%m.%Y %H:%M')
                interview_time_value = f"{start_str} - {end_str}"
            else:
                interview_time_value = start_str
            
            # Проверяем конфликты при выборе слота
            conflicting = check_conflicting_closed_slots(slot_start, slot_end)
            if conflicting:
                conflict_times = ', '.join([f"{c['start']} - {c['end']}" for c in conflicting])
                warning_message = f"⚠️ Внимание: между выбранным временем обнаружены занятые слоты: {conflict_times}"

        # Проверка на дубликаты анкет
        phone = data.get('phone', '').strip()
        telegram = data.get('telegram', '').strip()
        full_name = data.get('full_name', '').strip()
        
        duplicates = check_duplicate_applicants(phone, telegram, full_name)
        duplicate_warning = None
        
        if duplicates:
            # Формируем предупреждение о найденных дубликатах
            dup_info = []
            for dup in duplicates[:3]:  # Показываем максимум 3 первых совпадения
                status_text = {'pending': 'на рассмотрении', 'approved': 'одобрена', 'rejected': 'отклонена'}.get(dup['status'], dup['status'])
                dup_info.append(f"{dup['full_name']} (совпадение по: {dup['match_type']}, статус: {status_text}, добавлена: {dup['date_added']})")
            
            duplicate_warning = f"⚠️ ВНИМАНИЕ: Найдены похожие анкеты ({len(duplicates)} шт.): " + "; ".join(dup_info)
            if len(duplicates) > 3:
                duplicate_warning += f" и ещё {len(duplicates) - 3}..."

        new_applicant = Applicant(
            full_name=data.get('full_name', ''),
            date_of_birth=data.get('date_of_birth', ''),
            english_level=data.get('english_level', ''),
            cpu_model=data.get('cpu_model', ''),
            gpu_model=data.get('gpu_model', ''),
            internet_speed=data.get('internet_speed', ''),
            work_experience=data.get('work_experience', ''),
            interview_time=interview_time_value,
            phone=data.get('phone', ''),
            telegram=data.get('telegram', ''),
            owner_username=user.username if user else None,
            team=user.team if user else None
        )
        
        db.session.add(new_applicant)
        db.session.commit()
        
        response = {'success': True, 'message': 'Анкета успешно добавлена'}
        
        # Объединяем все предупреждения
        warnings = []
        if duplicate_warning:
            warnings.append(duplicate_warning)
        if warning_message:
            warnings.append(warning_message)
        
        if warnings:
            response['warning'] = '\n'.join(warnings)
        
        return jsonify(response), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/add-model-operator', methods=['POST'])
def add_model_operator():
    """Добавляет анкету модели/оператора"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
        user = User.query.get(session['user_id'])
        data = request.form  # Используем form для получения данных и файлов
        files = request.files  # Для загрузки фото
        
        # Валидация обязательных полей
        required_fields = ['full_name', 'city', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Поле "{field}" обязательно'}), 400
        
        # Сохраняем фото
        photos = []
        photo_dir = os.path.join('static', 'model_photos')
        os.makedirs(photo_dir, exist_ok=True)
        
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        
        if 'photos' in files:
            photo_files = files.getlist('photos')
            for idx, photo_file in enumerate(photo_files):
                if photo_file and photo_file.filename:
                    # Проверяем расширение файла
                    filename = secure_filename(photo_file.filename)
                    if '.' in filename:
                        ext = filename.rsplit('.', 1)[1].lower()
                        if ext not in ALLOWED_EXTENSIONS:
                            continue
                    else:
                        continue
                    
                    # Генерируем уникальное имя файла
                    timestamp = moscow_now().strftime('%Y%m%d_%H%M%S')
                    safe_filename = f'model_{user.id}_{timestamp}_{idx}_{filename}'
                    filepath = os.path.join(photo_dir, safe_filename)
                    
                    try:
                        photo_file.save(filepath)
                        photos.append(f'/static/model_photos/{safe_filename}')
                    except Exception as file_error:
                        print(f'Ошибка при сохранении файла: {file_error}')
                        continue
        
        # Создаём анкету
        new_model = ModelOperatorApplication(
            full_name=data.get('full_name', ''),
            city=data.get('city', ''),
            phone=data.get('phone', ''),
            age=data.get('age', ''),
            residence=data.get('residence', ''),
            has_dual_devices=data.get('has_dual_devices', ''),
            device_model=data.get('device_model', ''),
            work_hours=data.get('work_hours', ''),
            has_headphones=data.get('has_headphones', ''),
            telegram=data.get('telegram', ''),
            interview_time=data.get('interview_time', ''),  # Время собеседования модели
            photos=','.join(photos) if photos else '',
            owner_username=user.username if user else None,
            team=user.team if user else None
        )
        
        db.session.add(new_model)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Анкета модели/оператора успешно добавлена'}), 201
    except Exception as e:
        print(f'[ERROR] Ошибка при добавлении анкеты модели: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 400

@app.route('/api/add-chatter', methods=['POST'])
def add_chatter():
    """Добавляет анкету Чаттера"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
        user = User.query.get(session['user_id'])
        data = request.json
        
        # Валидация обязательных полей
        required_fields = ['full_name', 'age', 'geo', 'offer_number', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Поле "{field}" обязательно'}), 400
        
        # Создаём анкету
        new_chatter = ChatApplication(
            full_name=data.get('full_name', ''),
            age=data.get('age', ''),
            geo=data.get('geo', ''),
            experience=data.get('experience', ''),
            offer_number=data.get('offer_number', ''),
            phone=data.get('phone', ''),
            telegram=data.get('telegram', ''),
            owner_username=user.username if user else None,
            team=user.team if user else None
        )
        
        db.session.add(new_chatter)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Анкета Чаттера успешно добавлена'}), 201
    except Exception as e:
        print(f'[ERROR] Ошибка при добавлении анкеты Чаттера: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 400

@app.route('/api/applicants')
def get_applicants():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    
    # Модератор видит только анкеты своей команды
    if is_moderator_user(user):
        applicants = Applicant.query.filter_by(team=user.team, is_deleted=False).order_by(Applicant.date_added.desc()).all()
    # Owner и Developer видят все НЕ УДАЛЕННЫЕ анкеты
    elif user.is_owner or (user.prefix and user.prefix == 'Developer'):
        applicants = Applicant.query.filter_by(is_deleted=False).order_by(Applicant.date_added.desc()).all()
    # Обычные админы видят только НЕ УДАЛЕННЫЕ анкеты своей команды
    elif user.is_admin and user.team:
        applicants = Applicant.query.filter_by(team=user.team, is_deleted=False).order_by(Applicant.date_added.desc()).all()
        # Автоматически привязываем анкеты без команды к команде текущего админа
        for applicant in Applicant.query.filter_by(team=None, is_deleted=False).all():
            applicant.team = user.team
        db.session.commit()
    # Админы без команды видят все НЕ УДАЛЕННЫЕ анкеты (для обратной совместимости)
    elif user.is_admin:
        applicants = Applicant.query.filter_by(is_deleted=False).order_by(Applicant.date_added.desc()).all()
    # Обычные пользователи видят только свои НЕ УДАЛЕННЫЕ анкеты
    else:
        applicants = Applicant.query.filter_by(owner_username=user.username, is_deleted=False).order_by(Applicant.date_added.desc()).all()
    
    return jsonify([a.to_dict() for a in applicants])

@app.route('/api/model-operators')
def get_model_operators():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    
    # Модератор видит только анкеты своей команды
    if is_moderator_user(user):
        models = ModelOperatorApplication.query.filter(ModelOperatorApplication.is_deleted != True, ModelOperatorApplication.team == user.team).order_by(ModelOperatorApplication.date_added.desc()).all()
    # Owner и Developer видят все анкеты (кроме удаленных)
    elif user.is_owner or (user.prefix and user.prefix == 'Developer'):
        models = ModelOperatorApplication.query.filter(ModelOperatorApplication.is_deleted != True).order_by(ModelOperatorApplication.date_added.desc()).all()
    # Обычные админы видят только анкеты своей команды (кроме удаленных)
    elif user.is_admin and user.team:
        models = ModelOperatorApplication.query.filter(ModelOperatorApplication.is_deleted != True, ModelOperatorApplication.team == user.team).order_by(ModelOperatorApplication.date_added.desc()).all()
        # Автоматически привязываем анкеты без команды к команде текущего админа
        for model in ModelOperatorApplication.query.filter(ModelOperatorApplication.is_deleted != True, ModelOperatorApplication.team == None).all():
            model.team = user.team
        db.session.commit()
    # Админы без команды видят все анкеты (кроме удаленных)
    elif user.is_admin:
        models = ModelOperatorApplication.query.filter(ModelOperatorApplication.is_deleted != True).order_by(ModelOperatorApplication.date_added.desc()).all()
    # Обычные пользователи видят только свои анкеты (кроме удаленных)
    else:
        models = ModelOperatorApplication.query.filter(ModelOperatorApplication.is_deleted != True, ModelOperatorApplication.owner_username == user.username).order_by(ModelOperatorApplication.date_added.desc()).all()
    
    return jsonify([m.to_dict() for m in models])


@app.route('/api/public-scout-application', methods=['POST'])
def add_public_scout_application():
    """Публичная анкета для стримерш."""
    try:
        # Получаем данные из FormData (так как отправляется файл)
        full_name = (request.form.get('full_name') or '').strip()
        age = (request.form.get('age') or '').strip()
        city = (request.form.get('city') or '').strip()
        streaming_experience = (request.form.get('streaming_experience') or '').strip()
        motivation = (request.form.get('motivation') or '').strip()
        telegram_username = normalize_telegram_username((request.form.get('telegram_username') or '').strip())
        can_stream_change = (request.form.get('can_stream_change') or '').strip()
        device_model = (request.form.get('device_model') or '').strip()
        work_hours_per_week = (request.form.get('work_hours_per_week') or '').strip()

        # Для совместимости со старой схемой БД, где persuasion_text может быть NOT NULL.
        legacy_persuasion_text = motivation or f"Город: {city}. Опыт: {streaming_experience}."

        if not full_name:
            return jsonify({'success': False, 'message': 'Укажите имя'}), 400
        if not age:
            return jsonify({'success': False, 'message': 'Укажите дату рождения'}), 400
        try:
            birth_date = datetime.strptime(age, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Некорректная дата рождения'}), 400

        today = datetime.now().date()
        if birth_date > today:
            return jsonify({'success': False, 'message': 'Дата рождения не может быть в будущем'}), 400

        full_years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if full_years < 18:
            return jsonify({'success': False, 'message': 'Анкета доступна только с 18 лет'}), 400
        if not city:
            return jsonify({'success': False, 'message': 'Укажите город'}), 400
        if not streaming_experience:
            return jsonify({'success': False, 'message': 'Укажите опыт в стриминге'}), 400
        if not telegram_username:
            return jsonify({'success': False, 'message': 'Укажите Telegram'}), 400
        if not can_stream_change:
            return jsonify({'success': False, 'message': 'Ответьте: может ли кто-то поменять стриму'}), 400
        if not device_model:
            return jsonify({'success': False, 'message': 'Укажите модель устройства'}), 400
        if not work_hours_per_week:
            return jsonify({'success': False, 'message': 'Укажите часы и дни работы в неделю'}), 400

        # Обработка загрузки фото
        photo_file = request.files.get('photo')
        if not photo_file or not photo_file.filename:
            return jsonify({'success': False, 'message': 'Загрузите фото'}), 400

        if not is_allowed_scout_photo(photo_file.filename):
            return jsonify({'success': False, 'message': 'Допустимы только JPG, PNG или WEBP'}), 400

        content_type = (photo_file.content_type or '').lower()
        if not content_type.startswith('image/'):
            return jsonify({'success': False, 'message': 'Файл должен быть изображением'}), 400

        photo_url = None
        try:
            filename = secure_filename(photo_file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename

            # Создаем директорию для фото, если её нет
            upload_dir = os.path.join('static', 'scout_photos')
            os.makedirs(upload_dir, exist_ok=True)

            filepath = os.path.join(upload_dir, filename)
            photo_file.save(filepath)
            photo_url = f'/static/scout_photos/{filename}'
        except Exception as e:
            print(f'[WARNING] Ошибка при сохранении фото: {str(e)}')
            return jsonify({'success': False, 'message': 'Ошибка при загрузке фото'}), 400

        application = ScoutJoinApplication(
            full_name=full_name,
            age=age,
            persuasion_text=legacy_persuasion_text,
            city=city,
            streaming_experience=streaming_experience,
            motivation=motivation or None,
            telegram_username=telegram_username,
            can_stream_change=can_stream_change,
            device_model=device_model,
            work_hours_per_week=work_hours_per_week,
            photo_url=photo_url,
            work_time=f'{work_hours_per_week}'  # Сохраняем для совместимости
        )

        db.session.add(application)
        db.session.commit()
        
        # Отправляем подтверждающее уведомление в Telegram
        notify_sent = False
        notify_error = None
        if telegram_username:
            notify_sent, resolved_chat_id, notify_error = send_telegram_notification_sync(
                telegram_username,
                'submitted',
                None
            )
            if notify_sent and resolved_chat_id:
                application.telegram_chat_id = resolved_chat_id
                db.session.commit()
        
        response_data = {
            'success': True,
            'message': 'Анкета отправлена'
        }
        
        # Добавляем информацию о статусе уведомления (для отладки)
        if notify_sent:
            response_data['telegram_notified'] = True
        elif notify_error:
            response_data['telegram_warning'] = 'Анкета сохранена, но не удалось отправить уведомление. Напишите боту /start.'
        
        return jsonify(response_data), 201
    except Exception as e:
        print(f'[ERROR] Ошибка при отправке публичной анкеты: {str(e)}')
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 400

@app.route('/api/chatters')
def get_chatters():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    
    # Owner и Developer видят все анкеты (кроме удаленных)
    if user.is_owner or (user.prefix and user.prefix == 'Developer'):
        chatters = ChatApplication.query.filter(ChatApplication.is_deleted != True).order_by(ChatApplication.date_added.desc()).all()
    # Обычные админы видят только анкеты своей команды (кроме удаленных)
    elif user.is_admin and user.team:
        chatters = ChatApplication.query.filter(ChatApplication.is_deleted != True, ChatApplication.team == user.team).order_by(ChatApplication.date_added.desc()).all()
        # Автоматически привязываем анкеты без команды к команде текущего админа
        for chatter in ChatApplication.query.filter(ChatApplication.is_deleted != True, ChatApplication.team == None).all():
            chatter.team = user.team
        db.session.commit()
    # Админы без команды видят все анкеты (кроме удаленных)
    elif user.is_admin:
        chatters = ChatApplication.query.filter(ChatApplication.is_deleted != True).order_by(ChatApplication.date_added.desc()).all()
    # Обычные пользователи видят только свои анкеты (кроме удаленных)
    else:
        chatters = ChatApplication.query.filter(ChatApplication.is_deleted != True, ChatApplication.owner_username == user.username).order_by(ChatApplication.date_added.desc()).all()
    
    return jsonify([c.to_dict() for c in chatters])

@app.route('/api/interview-slots')
def get_interview_slots():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    include_all = request.args.get('all') == '1'
    slot_type = request.args.get('type', 'operator')  # По умолчанию получаем слоты для оператора

    print(f"📋 [API] get_interview_slots: include_all={include_all}, type={slot_type}")

    if include_all and user and user.is_admin:
        slots = InterviewSlot.query.filter_by(slot_type=slot_type).order_by(InterviewSlot.start_time.asc()).all()
    else:
        slots = InterviewSlot.query.filter_by(is_open=True, slot_type=slot_type).order_by(InterviewSlot.start_time.asc()).all()

    print(f"✅ [API] Возвращаю {len(slots)} слотов для типа '{slot_type}'")
    return jsonify({'success': True, 'slots': [s.to_dict() for s in slots]}), 200


@app.route('/api/calendar-availability')
def get_calendar_availability():
    """
    Получение информации о доступности по дням месяца.
    Возвращает для каждого дня: статус (green/red), кол-во свободных/занятых слотов
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        # Получаем год и месяц из параметров запроса
        year = request.args.get('year', moscow_now().year, type=int)
        month = request.args.get('month', moscow_now().month, type=int)
        slot_type = request.args.get('type', 'operator')  # По умолчанию operator
        
        print(f"📅 [API] get_calendar_availability: year={year}, month={month}, type={slot_type}")
        
        # Получаем все слоты для этого месяца и типа
        all_slots = InterviewSlot.query.filter_by(slot_type=slot_type).all()
        print(f"📊 [API] Найдено слотов для типа '{slot_type}': {len(all_slots)}")
        
        # Группируем слоты по дням
        days_status = {}
        
        for slot in all_slots:
            slot_date = slot.start_time
            
            # Учитываем только слоты текущего месяца
            if slot_date.year == year and slot_date.month == month:
                day = slot_date.day
                
                if day not in days_status:
                    days_status[day] = {
                        'open_slots': 0,
                        'closed_slots': 0,
                        'slots': []
                    }
                
                slot_info = {
                    'id': slot.id,
                    'start': slot.start_time.strftime('%H:%M'),
                    'end': slot.end_time.strftime('%H:%M') if slot.end_time else None,
                    'is_open': slot.is_open,
                    'slot_type': slot.slot_type
                }
                days_status[day]['slots'].append(slot_info)
                
                if slot.is_open:
                    days_status[day]['open_slots'] += 1
                else:
                    days_status[day]['closed_slots'] += 1
        
        # Определяем статус для каждого дня
        calendar_data = {}
        for day in range(1, 32):  # макс 31 день в месяце
            if day in days_status:
                day_info = days_status[day]
                # Если есть открытые слоты - зелёный
                # Если нет открытых но есть закрытые - красный
                # Если есть оба - все равно зелёный (приоритет открытым)
                if day_info['open_slots'] > 0:
                    status = 'green'
                else:
                    status = 'red'
                calendar_data[day] = {
                    'status': status,
                    'open_slots': day_info['open_slots'],
                    'closed_slots': day_info['closed_slots'],
                    'slots': day_info['slots']
                }
            else:
                # Если на день нет слотов - день серый (нет слотов)
                calendar_data[day] = {
                    'status': 'gray',
                    'open_slots': 0,
                    'closed_slots': 0,
                    'slots': []
                }
        
        return jsonify({
            'success': True,
            'year': year,
            'month': month,
            'calendar': calendar_data
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/interview-slots', methods=['POST'])
def create_interview_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        data = request.json
        start_raw = data.get('start_time')
        end_raw = data.get('end_time')
        slot_type = data.get('slot_type', 'operator')  # По умолчанию 'operator'
        
        if not start_raw:
            return jsonify({'success': False, 'message': 'Укажите дату и время начала'}), 400
        
        if slot_type not in ['operator', 'model']:
            return jsonify({'success': False, 'message': 'Неверный тип слота'}), 400

        start_time = datetime.fromisoformat(start_raw)
        end_time = datetime.fromisoformat(end_raw) if end_raw else None
        if end_time and end_time <= start_time:
            return jsonify({'success': False, 'message': 'Время окончания должно быть позже начала'}), 400

        slot = InterviewSlot(start_time=start_time, end_time=end_time, is_open=True, slot_type=slot_type)
        db.session.add(slot)
        db.session.commit()
        return jsonify({'success': True, 'slot': slot.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/interview-slots/delete-all', methods=['POST'])
@app.route('/api/slots/clear', methods=['POST'])
def delete_all_interview_slots():
    print('🗑️ [API] Запрос на удаление всех слотов')
    if 'user_id' not in session:
        print('❌ [API] Unauthorized - нет user_id в сессии')
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        print(f'❌ [API] Forbidden - пользователь {user.username if user else "None"} не админ')
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        deleted_count = InterviewSlot.query.count()
        print(f'📊 [API] Количество слотов для удаления: {deleted_count}')
        InterviewSlot.query.delete()
        db.session.commit()
        print(f'✅ [API] Успешно удалено {deleted_count} слотов')
        return jsonify({
            'success': True, 
            'message': f'Удалено {deleted_count} слотов',
            'deleted_count': deleted_count
        }), 200
    except Exception as e:
        print(f'❌ [API] Ошибка при удалении: {e}')
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/interview-slots/<int:slot_id>/close', methods=['POST'])
def close_interview_slot(slot_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        slot = InterviewSlot.query.get_or_404(slot_id)
        slot.is_open = False
        db.session.commit()
        return jsonify({'success': True, 'slot': slot.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/interview-slots/<int:slot_id>', methods=['DELETE'])
@app.route('/api/interview-slots/<int:slot_id>/delete', methods=['POST'])
def delete_interview_slot(slot_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        slot = InterviewSlot.query.get_or_404(slot_id)
        db.session.delete(slot)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Слот удалён'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/save-hours', methods=['POST'])
def admin_save_hours():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            print(f"❌ [Admin] No JSON data received")
            return jsonify({'success': False, 'message': 'Invalid data - no JSON'}), 400
            
        date_str = data.get('date')
        hours = data.get('hours', [])
        slot_type = data.get('slot_type', 'operator')  # 🔹 Получаем тип слота
        
        print(f"📝 [Admin] Received date_str={date_str}, hours={hours}, slot_type={slot_type}")
        
        if not date_str:
            return jsonify({'success': False, 'message': 'Date is required'}), 400
        if not hours or len(hours) == 0:
            return jsonify({'success': False, 'message': 'At least one hour is required'}), 400
        
        # Parse date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        # 🔹 КРИТИЧНО: Удаляем только слоты ЭТОГО ТИПА для этой даты!
        InterviewSlot.query.filter(
            db.func.date(InterviewSlot.start_time) == date_obj.date(),
            InterviewSlot.slot_type == slot_type  # 🔹 Фильтр по типу!
        ).delete()
        
        # Create new slots for each selected hour (hour:00 to hour+1:00)
        created_slots = []
        for hour in hours:
            try:
                hour = int(hour)
                start_time = datetime(date_obj.year, date_obj.month, date_obj.day, hour, 0, 0)
                end_time = datetime(date_obj.year, date_obj.month, date_obj.day, hour + 1, 0, 0)
                
                # 🔹 КРИТИЧНО: Указываем тип слота!
                slot = InterviewSlot(start_time=start_time, end_time=end_time, is_open=True, slot_type=slot_type)
                db.session.add(slot)
                created_slots.append(slot)
            except ValueError as e:
                print(f"❌ [Admin] Invalid hour value: {hour} - {e}")
                continue
        
        db.session.commit()
        print(f"✅ [Admin] Saved {len(created_slots)} hours for {date_str} (type: {slot_type})")
        
        return jsonify({
            'success': True, 
            'message': f'Saved {len(created_slots)} time slots',
            'slots_created': len(created_slots)
        }), 200
    except ValueError as e:
        db.session.rollback()
        print(f"❌ [Admin] ValueError: {e}")
        return jsonify({'success': False, 'message': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        print(f"❌ [Admin] Error saving hours: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/all-applicants')
def admin_get_all_applicants():
    """API для получения всех анкет, включая удаленные (только для админов)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        # Получаем ВСЕ анкеты без фильтрации по is_deleted
        applicants = Applicant.query.order_by(Applicant.date_added.desc()).all()
        return jsonify({
            'success': True,
            'applicants': [app.to_dict() for app in applicants]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/applicants-full-archive')
def admin_get_full_archive():
    """API для получения ПОЛНОГО АРХИВА всех анкет (когда-либо добавленных) - НИКАКИЕ НЕ УДАЛЯЮТСЯ"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        # Собираем ВСЕ анкеты из трёх таблиц
        all_records = []
        
        # 1. ОПЕРАТОРЫ (Applicant)
        operators = db.session.query(Applicant).all()
        for op in operators:
            record = op.to_dict()
            record['type'] = 'operator'
            record['type_emoji'] = '👨‍💼'
            record['type_name'] = 'Оператор'
            record['type_color'] = '#3b82f6'
            all_records.append(record)
        
        # 2. МОДЕЛИ (ModelOperatorApplication)
        models = db.session.query(ModelOperatorApplication).all()
        for model in models:
            record = model.to_dict()
            record['type'] = 'model'
            record['type_emoji'] = '👩‍🎬'
            record['type_name'] = 'Модель'
            record['type_color'] = '#ec4899'
            all_records.append(record)
        
        # 3. ЧАТТЕРЫ (ChatApplication)
        chatters = db.session.query(ChatApplication).all()
        for chatter in chatters:
            record = chatter.to_dict()
            record['type'] = 'chatter'
            record['type_emoji'] = '💬'
            record['type_name'] = 'Чаттер'
            record['type_color'] = '#8b5cf6'
            all_records.append(record)
        
        # 4. СТРИМЕРШИ (ScoutJoinApplication)
        scouters = db.session.query(ScoutJoinApplication).all()
        for scouter in scouters:
            record = scouter.to_dict()
            record['type'] = 'scouter'
            record['type_emoji'] = '🎥'
            record['type_name'] = 'Стримерша'
            record['type_color'] = '#10b981'
            all_records.append(record)
        
        # Сортируем по дате добавления (новые в начале)
        all_records.sort(key=lambda x: x['date_added'], reverse=True)
        
        return jsonify({
            'success': True,
            'total_count': len(all_records),
            'operators_count': len(operators),
            'models_count': len(models) + len(scouters),
            'chatters_count': len(chatters),
            'applicants': all_records
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/scouters')
def admin_get_scouters():
    """API для получения анкет скаутеров с landing (только для админов)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    
    # Модератор НЕ может видеть стримерш
    if is_moderator_user(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    if not can_access_admin_panel(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        # Администраторы видят все анкеты
        applications = ScoutJoinApplication.query.order_by(ScoutJoinApplication.date_added.desc()).all()
        return jsonify({
            'success': True,
            'count': len(applications),
            'applications': [application.to_dict() for application in applications]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/scouters/clear', methods=['POST'])
def admin_clear_scouters():
    """API для удаления всех анкет скаутеров (только для админов)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        applications = ScoutJoinApplication.query.all()
        count = len(applications)

        # Удаляем загруженные фото с диска перед очисткой таблицы.
        for application in applications:
            if not application.photo_url:
                continue
            filename = os.path.basename(application.photo_url)
            if not filename:
                continue
            file_path = os.path.join('static', 'scout_photos', filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as file_err:
                    print(f'[WARNING] Не удалось удалить фото {file_path}: {file_err}')

        ScoutJoinApplication.query.delete()
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Удалено анкет: {count}',
            'deleted_count': count
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/scout/<int:scout_id>/approve', methods=['POST'])
def admin_approve_scout(scout_id):
    """API для одобрения заявки скаутера (только для админов)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        application = ScoutJoinApplication.query.get(scout_id)
        if not application:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        application.status = 'approved'
        application.approved_by = user.username
        application.reviewed_at = moscow_now()
        db.session.commit()
        
        # Отправляем уведомление в Telegram
        notify_sent = False
        notify_error = None
        if application.telegram_username:
            notify_sent, resolved_chat_id, notify_error = send_telegram_notification_sync(
                application.telegram_username,
                'approved',
                application.telegram_chat_id
            )
            if notify_sent and resolved_chat_id and application.telegram_chat_id != resolved_chat_id:
                application.telegram_chat_id = resolved_chat_id
                db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Заявка одобрена',
            'telegram_notified': notify_sent,
            'telegram_error': notify_error,
            'application': application.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/scout/<int:scout_id>/reject', methods=['POST'])
def admin_reject_scout(scout_id):
    """API для отклонения заявки скаутера (только для админов)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        application = ScoutJoinApplication.query.get(scout_id)
        if not application:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        application.status = 'rejected'
        application.rejected_by = user.username
        application.reviewed_at = moscow_now()
        db.session.commit()
        
        # Отправляем уведомление в Telegram
        notify_sent = False
        notify_error = None
        if application.telegram_username:
            notify_sent, resolved_chat_id, notify_error = send_telegram_notification_sync(
                application.telegram_username,
                'rejected',
                application.telegram_chat_id
            )
            if notify_sent and resolved_chat_id and application.telegram_chat_id != resolved_chat_id:
                application.telegram_chat_id = resolved_chat_id
                db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Заявка отклонена',
            'telegram_notified': notify_sent,
            'telegram_error': notify_error,
            'application': application.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/users')
def admin_get_users():
    """API для получения списка всех пользователей (только для админов)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not has_full_admin_access(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return jsonify({
            'success': True,
            'count': len(users),
            'users': [u.to_dict() for u in users]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/admin/audit-logs')
def admin_get_audit_logs():
    """Чтение логов для вкладки аудита. Доступно только пользователям с префиксом Developer."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    if not is_developer_user(user):
        return jsonify({'success': False, 'message': 'Access denied: Developer only'}), 403

    log_type = (request.args.get('type') or 'audit').strip().lower()
    if log_type not in {'audit', 'app'}:
        return jsonify({'success': False, 'message': 'Неверный тип лога'}), 400

    lines_limit = request.args.get('limit', default=200, type=int)
    lines_limit = max(10, min(lines_limit, 1000))
    search_query = (request.args.get('q') or '').strip().lower()

    log_path = AUDIT_LOG_PATH if log_type == 'audit' else APP_LOG_PATH

    try:
        if not os.path.exists(log_path):
            return jsonify({
                'success': True,
                'type': log_type,
                'count': 0,
                'lines': []
            }), 200

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            if search_query:
                matched = [ln.rstrip('\n') for ln in f if search_query in ln.lower()]
                lines = matched[-lines_limit:]
            else:
                lines = [ln.rstrip('\n') for ln in deque(f, maxlen=lines_limit)]

        return jsonify({
            'success': True,
            'type': log_type,
            'count': len(lines),
            'lines': lines
        }), 200
    except Exception as e:
        logger.exception('Не удалось прочитать лог-файл: %s', log_path)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.permanent = remember_me
            session['user_id'] = user.id
            user.last_login_at = moscow_now()
            db.session.commit()
            audit_logger.info(
                'LOGIN_SUCCESS actor=%s user_id=%s action=login remember_me=%s event="%s" ip=%s ua="%s"',
                user.username,
                user.id,
                remember_me,
                _safe_log_text('Успешный вход в систему'),
                request.headers.get('X-Forwarded-For', request.remote_addr),
                _truncate_value(request.user_agent.string, limit=180)
            )
            flash('Успешный вход', 'success')
            if can_access_admin_panel(user):
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('dashboard'))
        else:
            audit_logger.warning(
                'LOGIN_FAILED actor=%s action=login_failed event="%s" ip=%s ua="%s"',
                username,
                _safe_log_text('Неудачная попытка входа'),
                request.headers.get('X-Forwarded-For', request.remote_addr),
                _truncate_value(request.user_agent.string, limit=180)
            )
            flash('Неверные учётные данные', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    username = 'anonymous'
    if user_id:
        user = User.query.get(user_id)
        if user:
            username = user.username

    audit_logger.info(
        'LOGOUT actor=%s user_id=%s action=logout event="%s" ip=%s ua="%s"',
        username,
        user_id,
        _safe_log_text('Выход из системы'),
        request.headers.get('X-Forwarded-For', request.remote_addr),
        _truncate_value(request.user_agent.string, limit=180)
    )
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        avatar_url = request.form.get('avatar_url', '').strip()
        crypto_wallet = request.form.get('crypto_wallet', '').strip()

        if display_name and len(display_name) > 120:
            flash('Имя слишком длинное (макс. 120 символов)', 'error')
            return redirect(url_for('profile'))
        if bio and len(bio) > 500:
            flash('Био слишком длинное (макс. 500 символов)', 'error')
            return redirect(url_for('profile'))
        if avatar_url:
            is_http = avatar_url.startswith('http://') or avatar_url.startswith('https://')
            is_static = avatar_url.startswith('/static/')
            if not is_http and not is_static:
                flash('Аватар: используйте ссылку http(s) или /static/', 'error')
                return redirect(url_for('profile'))

        user.display_name = display_name or None
        user.bio = bio or None
        user.avatar_url = avatar_url or None
        user.crypto_wallet = crypto_wallet or None
        db.session.commit()
        flash('Профиль обновлен', 'success')
        return redirect(url_for('profile'))

    # Статистика - считаем ВСЕ анкеты включая удаленные (статистика не должна меняться при удалении)
    operator_total = Applicant.query.filter_by(owner_username=user.username).count()
    operator_approved = Applicant.query.filter_by(owner_username=user.username, status='approved').count()
    operator_rejected = Applicant.query.filter_by(owner_username=user.username, status='rejected').count()

    model_total = ModelOperatorApplication.query.filter_by(owner_username=user.username).count()
    model_approved = ModelOperatorApplication.query.filter_by(owner_username=user.username, status='approved').count()
    model_rejected = ModelOperatorApplication.query.filter_by(owner_username=user.username, status='rejected').count()

    chatter_total = ChatApplication.query.filter_by(owner_username=user.username).count()
    chatter_approved = ChatApplication.query.filter_by(owner_username=user.username, status='approved').count()
    chatter_rejected = ChatApplication.query.filter_by(owner_username=user.username, status='rejected').count()

    stats = {
        'applicants_count': operator_total + model_total + chatter_total,
        'approved_applicants': operator_approved + model_approved + chatter_approved,
        'rejected_applicants': operator_rejected + model_rejected + chatter_rejected,
        'operators_total': operator_total,
        'operators_approved': operator_approved,
        'operators_rejected': operator_rejected,
        'models_total': model_total,
        'models_approved': model_approved,
        'models_rejected': model_rejected,
        'chatters_total': chatter_total,
        'chatters_approved': chatter_approved,
        'chatters_rejected': chatter_rejected
    }

    my_applications = get_user_applications(user.username)
    return render_template(
        'profile.html',
        current_user=user,
        stats=stats,
        is_admin_view=False,
        my_applications=my_applications
    )


@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@app.route('/admin/user/<int:user_id>/profile', methods=['GET', 'POST'])
def admin_view_user_profile(user_id):
    """Просмотр профиля пользователя админом или модератором"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not can_access_admin_panel(admin):
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Обработка POST запроса для обновления заработанной суммы
    if request.method == 'POST':
        earned_amount = request.form.get('earned_amount', '').strip()
        try:
            user.earned_amount = float(earned_amount) if earned_amount else 0.0
            db.session.commit()
            flash('Заработанная сумма обновлена', 'success')
        except ValueError:
            flash('Некорректная сумма', 'error')
        return redirect(url_for('admin_view_user_profile', user_id=user_id))
    
    # Получение статистики - считаем ВСЕ анкеты включая удаленные (статистика не должна меняться при удалении)
    operator_total = Applicant.query.filter_by(owner_username=user.username).count()
    operator_approved = Applicant.query.filter_by(owner_username=user.username, status='approved').count()
    operator_rejected = Applicant.query.filter_by(owner_username=user.username, status='rejected').count()

    model_total = ModelOperatorApplication.query.filter_by(owner_username=user.username).count()
    model_approved = ModelOperatorApplication.query.filter_by(owner_username=user.username, status='approved').count()
    model_rejected = ModelOperatorApplication.query.filter_by(owner_username=user.username, status='rejected').count()

    chatter_total = ChatApplication.query.filter_by(owner_username=user.username).count()
    chatter_approved = ChatApplication.query.filter_by(owner_username=user.username, status='approved').count()
    chatter_rejected = ChatApplication.query.filter_by(owner_username=user.username, status='rejected').count()

    stats = {
        'applicants_count': operator_total + model_total + chatter_total,
        'approved_applicants': operator_approved + model_approved + chatter_approved,
        'rejected_applicants': operator_rejected + model_rejected + chatter_rejected,
        'operators_total': operator_total,
        'operators_approved': operator_approved,
        'operators_rejected': operator_rejected,
        'models_total': model_total,
        'models_approved': model_approved,
        'models_rejected': model_rejected,
        'chatters_total': chatter_total,
        'chatters_approved': chatter_approved,
        'chatters_rejected': chatter_rejected
    }

    my_applications = get_user_applications(user.username)
    return render_template(
        'profile.html',
        current_user=user,
        stats=stats,
        is_admin_view=True,
        admin_user=admin,
        my_applications=my_applications
    )


@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not can_access_admin_panel(user):
        return redirect(url_for('dashboard'))
    
    # Модератор видит только пользователей своей команды
    if is_moderator_user(user):
        users = User.query.filter_by(team=user.team).order_by(User.created_at.desc()).all()
        default_tab = 'operators'
    # Полный админ видит всех пользователей
    elif has_full_admin_access(user):
        users = User.query.order_by(User.created_at.desc()).all()
        default_tab = 'users'
    else:
        users = []
        default_tab = 'operators'
    
    return render_template('admin.html', users=users, current_user=user, current_tab=default_tab)


@app.route('/admin/create-user', methods=['POST'])
def admin_create_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not can_access_admin_panel(admin):
        return redirect(url_for('dashboard'))
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin_role = request.form.get('is_admin') == 'on'
    is_moderator_role = request.form.get('is_moderator') == 'on'
    team = request.form.get('team')  # Получаем команду из формы
    
    if not username:
        flash('Введите логин', 'error')
        return redirect(url_for('admin_panel'))
    
    # Генерируем пароль, если его не предоставили
    if not password or password.strip() == '':
        password = generate_strong_password()
    
    if User.query.filter_by(username=username).first():
        flash('Пользователь с таким именем уже существует', 'error')
        return redirect(url_for('admin_panel'))

    # Модератор может создавать только рабочие аккаунты.
    if is_moderator_user(admin) and (is_admin_role or is_moderator_role):
        flash('Модератор может создавать только рабочие аккаунты', 'error')
        return redirect(url_for('admin_panel'))

    new_prefix = None
    if is_moderator_role:
        is_admin_role = False
        new_prefix = 'Moderator'
    
    new_user = User(
        username=username,
        password_hash=generate_password_hash(password),
        is_admin=is_admin_role,
        prefix=new_prefix,
        team=team
    )
    db.session.add(new_user)
    db.session.commit()
    
    if is_moderator_role:
        user_type = 'модератор'
    elif is_admin_role:
        user_type = 'администратор'
    else:
        user_type = 'рабочий'
    
    flash(f'{user_type.capitalize()} {username} создан. Пароль: {password}', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not has_full_admin_access(admin):
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Защита владельца - только владелец может удалить другого владельца
    if user.is_owner and not admin.is_owner:
        flash('Нельзя удалить владельца', 'error')
        return redirect(url_for('admin_panel'))
    
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удалён', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/api/reset-password/<int:user_id>', methods=['POST'])
def reset_user_password(user_id):
    """Сброс пароля пользователя и возврат нового пароля"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    admin = User.query.get(session['user_id'])
    if not has_full_admin_access(admin):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Защита владельца - только владелец может сбросить пароль другому владельцу
        if user.is_owner and not admin.is_owner:
            return jsonify({'success': False, 'message': 'Нельзя сбросить пароль владельца'}), 403
        
        # Генерируем новый пароль
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        print(f"[INFO] Сброс пароля для пользователя {user.username}")
        print(f"[INFO] Новый пароль: {new_password}")
        
        return jsonify({
            'success': True, 
            'message': 'Пароль сброшен',
            'new_password': new_password,
            'username': user.username
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/api/update-team/<int:user_id>', methods=['POST'])
def update_user_team(user_id):
    """Изменение команды пользователя"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    admin = User.query.get(session['user_id'])
    if not has_full_admin_access(admin):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        new_team = data.get('team', '')
        
        # Валидация команды
        valid_teams = ['Delta', 'Den', 'ХАЦКЕР', '404', 'Bobik', 'Oir', 'Gordon', 'Rey', '']
        if new_team not in valid_teams:
            return jsonify({'success': False, 'message': 'Неверная команда'}), 400
        
        # Обновляем команду
        user.team = new_team if new_team else None
        db.session.commit()
        
        print(f"[INFO] Команда пользователя {user.username} изменена на: {new_team or 'Без команды'}")
        
        return jsonify({
            'success': True, 
            'message': 'Команда обновлена',
            'team': new_team,
            'username': user.username
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/delete/<int:applicant_id>', methods=['DELETE'])
def delete_applicant(applicant_id):
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        applicant = Applicant.query.get_or_404(applicant_id)
        # allow admin or owner
        if not user.is_admin and applicant.owner_username != user.username:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        # Мягкое удаление - помечаем как удаленную, но не удаляем физически
        applicant.is_deleted = True
        db.session.commit()
        return jsonify({'success': True, 'message': 'Запись удалена'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/delete-model/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        model = ModelOperatorApplication.query.get_or_404(model_id)
        # allow admin or owner
        if not user.is_admin and model.owner_username != user.username:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        # Мягкое удаление - только помечаем isdead флаг
        model.is_deleted = True
        db.session.commit()
        return jsonify({'success': True, 'message': 'Анкета модели удалена'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/applicant/<int:applicant_id>/status', methods=['POST'])
def update_applicant_status(applicant_id):
    """Изменение статуса анкеты (одобрить/отклонить)"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        applicant = Applicant.query.get_or_404(applicant_id)
        data = request.json
        status = data.get('status')
        
        if status not in ['pending', 'approved', 'rejected']:
            return jsonify({'success': False, 'message': 'Некорректный статус'}), 400
        
        applicant.status = status
        db.session.commit()
        
        status_text = {'pending': 'Ожидает', 'approved': 'Одобрена', 'rejected': 'Отклонена'}
        return jsonify({'success': True, 'message': f'Статус изменен: {status_text[status]}', 'status': status}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/applicant/<int:applicant_id>', methods=['GET'])
def get_applicant(applicant_id):
    """Получение данных анкеты для редактирования"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
        applicant = Applicant.query.get_or_404(applicant_id)
        user = User.query.get(session['user_id'])
        
        # Проверка прав: владелец или админ
        if not (user.is_admin or applicant.owner_username == user.username):
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        return jsonify({'success': True, 'applicant': applicant.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/applicant/<int:applicant_id>', methods=['PUT'])
def update_applicant(applicant_id):
    """Обновление данных анкеты (только для анкет в статусе pending)"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
        applicant = Applicant.query.get_or_404(applicant_id)
        user = User.query.get(session['user_id'])
        
        # Проверка прав: владелец или админ
        if not (user.is_admin or applicant.owner_username == user.username):
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        # Можно редактировать только анкеты в статусе pending
        if applicant.status != 'pending':
            return jsonify({'success': False, 'message': 'Можно редактировать только анкеты в статусе ожидания'}), 400
        
        data = request.json
        
        # Обновляем поля
        if 'full_name' in data:
            applicant.full_name = data['full_name']
        if 'date_of_birth' in data:
            applicant.date_of_birth = data['date_of_birth']
        if 'english_level' in data:
            applicant.english_level = data['english_level']
        if 'cpu_model' in data:
            applicant.cpu_model = data['cpu_model']
        if 'gpu_model' in data:
            applicant.gpu_model = data['gpu_model']
        if 'internet_speed' in data:
            applicant.internet_speed = data['internet_speed']
        if 'work_experience' in data:
            applicant.work_experience = data['work_experience']
        if 'interview_time' in data:
            applicant.interview_time = data['interview_time']
        if 'phone' in data:
            applicant.phone = data['phone']
        if 'telegram' in data:
            applicant.telegram = data['telegram']
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Анкета успешно обновлена', 'applicant': applicant.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/model-operator/<int:model_id>/status', methods=['POST'])
def update_model_operator_status(model_id):
    """Изменение статуса анкеты модели/оператора (одобрить/отклонить)"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        model = ModelOperatorApplication.query.get_or_404(model_id)
        data = request.json
        status = data.get('status')
        
        if status not in ['pending', 'approved', 'rejected']:
            return jsonify({'success': False, 'message': 'Некорректный статус'}), 400
        
        model.status = status
        db.session.commit()
        
        status_text = {'pending': 'Ожидает', 'approved': 'Одобрена', 'rejected': 'Отклонена'}
        return jsonify({'success': True, 'message': f'Статус изменен: {status_text[status]}', 'status': status}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/delete-chatter/<int:chatter_id>', methods=['DELETE'])
def delete_chatter(chatter_id):
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        chatter = ChatApplication.query.get_or_404(chatter_id)
        # allow admin or owner
        if not user.is_admin and chatter.owner_username != user.username:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        # Мягкое удаление - только помечаем флаг
        chatter.is_deleted = True
        db.session.commit()
        return jsonify({'success': True, 'message': 'Анкета Чаттера удалена'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/chatter/<int:chatter_id>/status', methods=['POST'])
def update_chatter_status(chatter_id):
    """Изменение статуса анкеты Чаттера (одобрить/отклонить)"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            return jsonify({'success': False, 'message': 'Forbidden'}), 403
        
        chatter = ChatApplication.query.get_or_404(chatter_id)
        data = request.json
        status = data.get('status')
        
        if status not in ['pending', 'approved', 'rejected']:
            return jsonify({'success': False, 'message': 'Некорректный статус'}), 400
        
        chatter.status = status
        db.session.commit()
        
        status_text = {'pending': 'Ожидает', 'approved': 'Одобрена', 'rejected': 'Отклонена'}
        return jsonify({'success': True, 'message': f'Статус изменен: {status_text[status]}', 'status': status}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/delete-all', methods=['DELETE'])
def delete_all_applicants():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        user = User.query.get(session['user_id'])
        if not user:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        if not user.is_admin and not user.is_owner and not (user.prefix and user.prefix == 'Developer'):
            return jsonify({'success': False, 'message': 'Forbidden'}), 403

        statuses_to_delete = ['approved', 'rejected']

        # Owner и Developer могут очищать все доступные анкеты
        if user.is_owner or (user.prefix and user.prefix == 'Developer'):
            applicants = Applicant.query.filter(
                Applicant.status.in_(statuses_to_delete),
                Applicant.is_deleted == False
            ).all()
            success_scope = 'по всем командам'
        # Обычный админ очищает только анкеты своей команды
        elif user.team:
            applicants = Applicant.query.filter(
                Applicant.team == user.team,
                Applicant.status.in_(statuses_to_delete),
                Applicant.is_deleted == False
            ).all()
            success_scope = f'в команде "{user.team}"'
        else:
            return jsonify({'success': False, 'message': 'Для очистки назначьте админу команду'}), 400

        deleted_count = 0
        for applicant in applicants:
            applicant.is_deleted = True
            deleted_count += 1
        db.session.commit()
        return jsonify({'success': True, 'message': f'Удалено {deleted_count} анкет со статусами "Одобрено" и "Отклонено" {success_scope}. Анкеты со статусом "Ожидает" сохранены.'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/download-report')
def download_report():
    try:
        # Получаем все НЕ УДАЛЕННЫЕ анкеты, кроме отклоненных (rejected)
        applicants = Applicant.query.filter(Applicant.status != 'rejected', Applicant.is_deleted == False).order_by(Applicant.date_added.desc()).all()
        
        # Создание текстового отчета
        report_content = "=" * 80 + "\n"
        report_content += "ОТЧЕТ ПО КАНДИДАТАМ\n"
        report_content += f"Дата создания: {moscow_now().strftime('%d.%m.%Y %H:%M')}\n"
        report_content += f"Всего кандидатов: {len(applicants)}\n"
        report_content += "=" * 80 + "\n\n"
        
        for idx, applicant in enumerate(applicants, 1):
            report_content += f"Добавил: {applicant.owner_username}\n"
            report_content += f"КАНДИДАТ #{idx}\n"
            report_content += "-" * 80 + "\n"
            report_content += f"Имя: {applicant.full_name}\n"
            report_content += f"Возраст (Дата рождения): {applicant.date_of_birth}\n"
            report_content += f"Знание английского языка: {applicant.english_level}\n"
            report_content += f"Модель процессора: {applicant.cpu_model}\n"
            report_content += f"Модель видеокарты: {applicant.gpu_model}\n"
            report_content += f"Скорость Интернета: {applicant.internet_speed}\n"
            report_content += f"Где работал/ла: {applicant.work_experience}\n"
            report_content += f"Время собеседования: {applicant.interview_time}\n"
            report_content += f"Телефон: {applicant.phone}\n"
            report_content += f"Телега: {applicant.telegram}\n"
            report_content += f"Дата добавления: {applicant.date_added.strftime('%d.%m.%Y %H:%M')}\n"
            report_content += "\n"
        
        # Отправка файла
        file_stream = io.BytesIO(report_content.encode('utf-8'))
        return send_file(
            file_stream,
            mimetype='text/plain; charset=utf-8',
            as_attachment=True,
            download_name=f'report_{moscow_now().strftime("%d_%m_%Y_%H_%M")}.txt'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/download-models-report')
def download_models_report():
    try:
        # Получаем все анкеты моделей, кроме отклоненных (rejected)
        models = ModelOperatorApplication.query.filter(ModelOperatorApplication.status != 'rejected').order_by(ModelOperatorApplication.date_added.desc()).all()
        
        # Создание текстового отчета
        report_content = "=" * 80 + "\n"
        report_content += "ОТЧЕТ ПО МОДЕЛЯМ/ОПЕРАТОРАМ\n"
        report_content += f"Дата создания: {moscow_now().strftime('%d.%m.%Y %H:%M')}\n"
        report_content += f"Всего моделей: {len(models)}\n"
        report_content += "=" * 80 + "\n\n"
        
        for idx, model in enumerate(models, 1):
            report_content += f"Добавил: {model.owner_username}\n"
            report_content += f"МОДЕЛЬ/ОПЕРАТОР #{idx}\n"
            report_content += "-" * 80 + "\n"
            report_content += f"Имя: {model.full_name}\n"
            report_content += f"Город: {model.city}\n"
            report_content += f"Телефон: {model.phone}\n"
            report_content += f"Возраст: {model.age}\n"
            report_content += f"Проживание: {model.residence}\n"
            report_content += f"2 устройства: {model.has_dual_devices}\n"
            report_content += f"Модель устройства: {model.device_model}\n"
            report_content += f"Часы/дни в неделю: {model.work_hours}\n"
            report_content += f"Наушники: {model.has_headphones}\n"
            report_content += f"Телега: {model.telegram}\n"
            report_content += f"Статус: {model.status}\n"
            report_content += f"Дата добавления: {model.date_added.strftime('%d.%m.%Y %H:%M')}\n"
            report_content += "\n"
        
        # Отправка файла
        file_stream = io.BytesIO(report_content.encode('utf-8'))
        return send_file(
            file_stream,
            mimetype='text/plain; charset=utf-8',
            as_attachment=True,
            download_name=f'models_report_{moscow_now().strftime("%d_%m_%Y_%H_%M")}.txt'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/delete-all-answers', methods=['POST'])
def delete_all_answers():
    """Удаление всех ответов гостей"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    try:
        # Получаем таблицу из инспектора
        from sqlalchemy import inspect
        insp = inspect(db.engine)
        
        if 'guest_answer' in insp.get_table_names():
            # Удаляем все ответы
            db.session.execute(text("DELETE FROM guest_answer"))
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Все ответы гостей удалены'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Таблица ответов не найдена'
            }), 404
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Ошибка при удалении ответов: {e}")
        return jsonify({
            'success': False,
            'message': f'Ошибка при удалении: {str(e)}'
        }), 400

if __name__ == '__main__':
    import os
    
    # Проверяем окружение
    env = os.environ.get('FLASK_ENV', 'development')
    debug_mode = env == 'development'
    
    if debug_mode:
        print("🚀 Запуск в режиме РАЗРАБОТКИ...")
        # Создание ngrok туннеля для удалённого доступа
        ngrok.set_auth_token("3A6zQHpsbYHKmKlLBDvJY3fKBXb_QrX2cmrP2Qufh6GmeRTY")
        print("🔧 Настройка ngrok...")
        try:
            # Убиваем все существующие туннели
            print("🔄 Останавливаю старые туннели...")
            ngrok.kill()
            import time
            time.sleep(2)
            
            # Создаём новый туннель с новым случайным доменом
            print("🌐 Создаю новый туннель...")
            public_url = ngrok.connect(5000, bind_tls=True)
            print(f"\n{'='*60}")
            print(f"✅ Ваш НОВЫЙ публичный URL:")
            print(f"🌐 {public_url}")
            print(f"{'='*60}")
            print(f"📱 Поделитесь этой ссылкой с другими людьми")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"⚠️ Ошибка ngrok: {e}")
            print("Запускаю приложение в режиме локальной сети...\n")
        
        # Запуск без auto-reloader чтобы избежать конфликтов с ngrok
        print("🏁 Запуск Flask сервера...")
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    else:
        print("🌍 Запуск в режиме PRODUCTION...")
        app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
