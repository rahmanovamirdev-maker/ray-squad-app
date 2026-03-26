
import os
try:
    from pyngrok import ngrok
except ImportError:
    ngrok = None
INSTANCE_DIR = os.path.join(os.path.dirname(__file__), 'instance')
APP_LOG_PATH = os.path.join(INSTANCE_DIR, 'app.log')
AUDIT_LOG_PATH = os.path.join(INSTANCE_DIR, 'audit.log')
VALID_TEAMS = [
    'Delta', 'Den', 'ХАЦКЕР', '404', 'Bobik', 'Oir', 'Gordon', 'Rey'
]
TEAM_EMOJI_MAP = {
    'Delta': '🔴',
    'Den': '🔵',
    'ХАЦКЕР': '🟢',
    '404': '🟡',
    'Bobik': '🟣',
    'Oir': '🟠',
    'Gordon': '⚫',
    'Rey': '💎'
}
LOGIN_ACCESS_RESTRICTED = True
LOGIN_ACCESS_RESTRICTED_MESSAGE = 'Доступ временно ограничен. Вход в панель сейчас закрыт.'
INSTANCE_DIR = os.path.join(os.path.dirname(__file__), 'instance')
VALID_TEAMS = [
    'Delta', 'Den', 'ХАЦКЕР', '404', 'Bobik', 'Oir', 'Gordon', 'Rey'
]
import re
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash, g, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from email.message import EmailMessage
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
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
db = SQLAlchemy(app)

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
    ref_token = db.Column(db.String(32), unique=True, nullable=True)  # Уникальный реферальный токен

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


class TeamCore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(50), nullable=False)
    core_index = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    lead_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=moscow_now)

    lead_user = db.relationship('User', foreign_keys=[lead_user_id], lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('team_name', 'core_index', name='uq_team_core'),
    )


class TeamSubCore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    core_id = db.Column(db.Integer, db.ForeignKey('team_core.id'), nullable=False)
    subcore_index = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    lead_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=moscow_now)

    core = db.relationship('TeamCore', backref=db.backref('subcores', lazy=True, cascade='all, delete-orphan'))
    lead_user = db.relationship('User', foreign_keys=[lead_user_id], lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('core_id', 'subcore_index', name='uq_team_subcore'),
    )


class TeamAcademSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subcore_id = db.Column(db.Integer, db.ForeignKey('team_sub_core.id'), nullable=False)
    slot_index = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, unique=True)
    assigned_at = db.Column(db.DateTime, nullable=True)

    subcore = db.relationship('TeamSubCore', backref=db.backref('academ_slots', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('subcore_id', 'slot_index', name='uq_team_academ_slot'),
    )

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


# --- Новые статусы анкет (на русском) ---

# --- Новые статусы анкет (на русском, 2026) ---
APPLICATION_STATUS_ON_REVIEW = 'На рассмотрении'  # По умолчанию
APPLICATION_STATUS_TRAINING = 'На обучении'
APPLICATION_STATUS_REGISTRATION = 'На регистрации'
APPLICATION_STATUS_DECLINED_CANDIDATE = 'Отказ со стороны кандидата'
APPLICATION_STATUS_DECLINED_PARTNER = 'Отказ со стороны партнера'
APPLICATION_STATUS_NO_SHOW = 'Не пришел/ла'

# Список всех новых статусов для справки
APPLICATION_STATUSES = [
    APPLICATION_STATUS_ON_REVIEW,
    APPLICATION_STATUS_TRAINING,
    APPLICATION_STATUS_REGISTRATION,
    APPLICATION_STATUS_DECLINED_CANDIDATE,
    APPLICATION_STATUS_DECLINED_PARTNER,
    APPLICATION_STATUS_NO_SHOW
]

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
    # Возможные статусы: На рассмотрении, Одобрена, Отклонена, В команде, Покинул(а) команду
    status = db.Column(db.String(32), default=APPLICATION_STATUS_ON_REVIEW)
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
    status = db.Column(db.String(32), default=APPLICATION_STATUS_ON_REVIEW)  # На рассмотрении, Одобрена, Отклонена, В команде, Покинул(а) команду
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
    ref_code = db.Column(db.String(120), nullable=True)
    referred_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    referred_by_username = db.Column(db.String(80), nullable=True)
    date_added = db.Column(db.DateTime, default=moscow_now)
    status = db.Column(db.String(32), default=APPLICATION_STATUS_ON_REVIEW)  # На рассмотрении, Одобрена, Отклонена, В команде, Покинул(а) команду
    approved_by = db.Column(db.String(120), nullable=True)
    rejected_by = db.Column(db.String(120), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    team = db.Column(db.String(50), nullable=True)  # Команда (Team 1 - Team 8)
    is_deleted = db.Column(db.Boolean, default=False)  # Мягкое удаление

    referred_by_user = db.relationship('User', foreign_keys=[referred_by_user_id], lazy='joined')

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
            'ref_code': self.ref_code,
            'referred_by_user_id': self.referred_by_user_id,
            'referred_by_username': self.referred_by_username,
            'date_added': self.date_added.strftime('%d.%m.%Y %H:%M') if self.date_added else None,
            'status': self.status or APPLICATION_STATUS_ON_REVIEW,
            'approved_by': self.approved_by,
            'rejected_by': self.rejected_by,
            'reviewed_at': self.reviewed_at.strftime('%d.%m.%Y %H:%M') if self.reviewed_at else None,
            'team': self.team,
            'is_deleted': self.is_deleted if hasattr(self, 'is_deleted') else False
        }


def ensure_team_structure_seed(team_name=None):
    """Создает стартовую структуру только если у команды вообще нет основ."""
    changed = False

    if team_name and team_name in VALID_TEAMS:
        team_names = [team_name]
    else:
        team_names = list(VALID_TEAMS)

    for target_team in team_names:
        existing_core = TeamCore.query.filter_by(team_name=target_team).first()
        if existing_core:
            continue

        core = TeamCore(team_name=target_team, core_index=1, title='Основа 1')
        db.session.add(core)
        db.session.flush()

        subcore = TeamSubCore(core_id=core.id, subcore_index=1, title='Под-основа 1.1')
        db.session.add(subcore)
        db.session.flush()

        db.session.add(TeamAcademSlot(subcore_id=subcore.id, slot_index=1))
        changed = True

    if changed:
        db.session.commit()


def renumber_team_structure(team_name):
    """Нормализует индексы и фиксированные названия после CRUD-операций."""
    cores = TeamCore.query.filter_by(team_name=team_name).order_by(TeamCore.core_index.asc(), TeamCore.id.asc()).all()
    for core_position, core in enumerate(cores, start=1):
        core.core_index = core_position
        core.title = f'Основа {core_position}'

        subcores = TeamSubCore.query.filter_by(core_id=core.id).order_by(TeamSubCore.subcore_index.asc(), TeamSubCore.id.asc()).all()
        for subcore_position, subcore in enumerate(subcores, start=1):
            subcore.subcore_index = subcore_position
            subcore.title = f'Под-основа {core_position}.{subcore_position}'

            slots = TeamAcademSlot.query.filter_by(subcore_id=subcore.id).order_by(TeamAcademSlot.slot_index.asc(), TeamAcademSlot.id.asc()).all()
            for slot_position, slot in enumerate(slots, start=1):
                slot.slot_index = slot_position

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
            if 'ref_token' not in cols:
                print("[MIGRATION] Добавляю столбец ref_token в таблицу user...")
                db.session.execute(text("ALTER TABLE user ADD COLUMN ref_token VARCHAR(32)"))
                db.session.commit()
                print("[MIGRATION] Столбец ref_token добавлен успешно")
            # Генерируем токены для существующих пользователей, у которых их нет
            users_without_token = User.query.filter(User.ref_token == None).all()
            if users_without_token:
                for _u in users_without_token:
                    _u.ref_token = secrets.token_hex(8)
                db.session.commit()
                print(f"[MIGRATION] ref_token сгенерирован для {len(users_without_token)} пользователей")
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
            if 'ref_code' not in cols:
                print("[MIGRATION] Добавляю столбец ref_code в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN ref_code VARCHAR(120)"))
                db.session.commit()
            if 'referred_by_user_id' not in cols:
                print("[MIGRATION] Добавляю столбец referred_by_user_id в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN referred_by_user_id INTEGER"))
                db.session.commit()
            if 'referred_by_username' not in cols:
                print("[MIGRATION] Добавляю столбец referred_by_username в таблицу scout_join_application...")
                db.session.execute(text("ALTER TABLE scout_join_application ADD COLUMN referred_by_username VARCHAR(80)"))
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
        if 'team_core' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('team_core')]
            if 'lead_user_id' not in cols:
                print("[MIGRATION] Добавляю столбец lead_user_id в таблицу team_core...")
                db.session.execute(text("ALTER TABLE team_core ADD COLUMN lead_user_id INTEGER"))
                db.session.commit()
                print("[MIGRATION] Столбец lead_user_id добавлен в team_core")
        if 'team_sub_core' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('team_sub_core')]
            if 'lead_user_id' not in cols:
                print("[MIGRATION] Добавляю столбец lead_user_id в таблицу team_sub_core...")
                db.session.execute(text("ALTER TABLE team_sub_core ADD COLUMN lead_user_id INTEGER"))
                db.session.commit()
                print("[MIGRATION] Столбец lead_user_id добавлен в team_sub_core")
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

    try:
        ensure_team_structure_seed()
    except Exception as e:
        print(f"[TEAM STRUCTURE SEED ERROR] {str(e)}")
        db.session.rollback()

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
    if not user:
        return False
    normalized_prefix = (user.prefix or '').strip().lower()
    return normalized_prefix in {'moderator', 'модератор'}


def can_access_admin_panel(user):
    return bool(user and (user.is_admin or is_moderator_user(user) or user.is_owner or is_developer_user(user)))


def can_access_team_stats_tab(user):
    return bool(user and (user.is_owner or is_developer_user(user)))


def has_full_admin_access(user):
    return bool(user and user.is_admin and not is_moderator_user(user))


def is_global_team_manager(user):
    """Глобальный менеджер может управлять всеми командами."""
    if not user:
        return False
    if user.is_owner or is_developer_user(user):
        return True
    # Админ без привязки к команде считается глобальным менеджером для обратной совместимости.
    return bool(user.is_admin and not is_moderator_user(user) and not user.team)


def is_team_admin(user):
    """Админ команды: не модератор, с привязкой к валидной команде."""
    return bool(
        user
        and user.is_admin
        and not is_moderator_user(user)
        and user.team in VALID_TEAMS
    )


def get_user_managed_teams(user):
    """Список команд, которыми пользователь может управлять в панели структуры."""
    if not user:
        return set()

    # Владелец и Developer имеют полный доступ ко всем командам.
    if user.is_owner or is_developer_user(user):
        return set(VALID_TEAMS)

    # Админ команды управляет только своей командой.
    if is_team_admin(user):
        return {user.team}

    return set()


def can_access_team_panel(user):
    if not user:
        return False
    # Владелец, Developer и full-admin имеют безусловный доступ к панели команды.
    if user.is_owner or is_developer_user(user) or has_full_admin_access(user):
        return True
    if is_moderator_user(user):
        return False
    return bool(get_user_managed_teams(user))


def can_administer_team(user, team_name):
    """Может полностью администрировать команду (назначения лидов, любые изменения)."""
    if not user or not team_name:
        return False
    if user.is_owner or is_developer_user(user):
        return True
    return bool(is_team_admin(user) and user.team == team_name)


def can_manage_core(user, core):
    if not user or not core:
        return False
    return bool(can_administer_team(user, core.team_name))


def can_manage_subcore(user, subcore):
    if not user or not subcore:
        return False
    core = TeamCore.query.get(subcore.core_id)
    if not core:
        return False
    return bool(can_administer_team(user, core.team_name))


def get_user_team_structure_position(user):
    """Возвращает положение пользователя в командной структуре."""
    position = {
        'team_name': (user.team or '').strip() if user else '',
        'core_title': '',
        'core_index': None,
        'subcore_title': '',
        'subcore_index': None,
        'slot_index': None,
        'roles': [],
        'has_structure': False,
    }

    if not user:
        return position

    core_lead = TeamCore.query.filter_by(lead_user_id=user.id).first()
    subcore_lead = (
        db.session.query(TeamSubCore)
        .join(TeamCore, TeamCore.id == TeamSubCore.core_id)
        .filter(TeamSubCore.lead_user_id == user.id)
        .first()
    )
    slot = (
        db.session.query(TeamAcademSlot)
        .join(TeamSubCore, TeamSubCore.id == TeamAcademSlot.subcore_id)
        .join(TeamCore, TeamCore.id == TeamSubCore.core_id)
        .filter(TeamAcademSlot.user_id == user.id)
        .first()
    )

    if core_lead:
        position['team_name'] = core_lead.team_name or position['team_name']
        position['core_title'] = core_lead.title or ''
        position['core_index'] = core_lead.core_index
        position['roles'].append('Лид основы')
        position['has_structure'] = True

    if subcore_lead:
        position['team_name'] = subcore_lead.core.team_name or position['team_name']
        position['core_title'] = subcore_lead.core.title or position['core_title']
        position['core_index'] = subcore_lead.core.core_index
        position['subcore_title'] = subcore_lead.title or ''
        position['subcore_index'] = subcore_lead.subcore_index
        position['roles'].append('Лид подосновы')
        position['has_structure'] = True

    if slot:
        position['team_name'] = slot.subcore.core.team_name or position['team_name']
        position['core_title'] = slot.subcore.core.title or position['core_title']
        position['core_index'] = slot.subcore.core.core_index
        position['subcore_title'] = slot.subcore.title or position['subcore_title']
        position['subcore_index'] = slot.subcore.subcore_index
        position['slot_index'] = slot.slot_index
        position['roles'].append('Участник слота')
        position['has_structure'] = True

    if not position['roles']:
        if position['team_name']:
            position['roles'].append('Участник команды')
        else:
            position['roles'].append('Без назначения')

    position['roles'] = list(dict.fromkeys(position['roles']))
    return position


def resolve_team_for_panel(actor, requested_team=None):
    if not actor:
        return None

    managed_teams = sorted(get_user_managed_teams(actor))
    if not managed_teams:
        return None

    team_name = (requested_team or '').strip()
    if team_name and team_name in managed_teams:
        return team_name

    if actor.team in managed_teams:
        return actor.team

    return managed_teams[0]


def build_team_structure_payload(team_name):
    cores = TeamCore.query.filter_by(team_name=team_name).order_by(TeamCore.core_index.asc()).all()
    payload = []

    for core in cores:
        subcore_rows = TeamSubCore.query.filter_by(core_id=core.id).order_by(TeamSubCore.subcore_index.asc()).all()
        subcores_payload = []

        for subcore in subcore_rows:
            slot_rows = TeamAcademSlot.query.filter_by(subcore_id=subcore.id).order_by(TeamAcademSlot.slot_index.asc()).all()
            slots_payload = []
            for slot in slot_rows:
                slots_payload.append({
                    'id': slot.id,
                    'slot_index': slot.slot_index,
                    'user_id': slot.user_id,
                    'username': slot.user.username if slot.user else None,
                    'display_name': slot.user.display_name if slot.user else None,
                    'prefix': slot.user.prefix if slot.user else None,
                    'is_admin': bool(slot.user.is_admin) if slot.user else False
                })

            subcores_payload.append({
                'id': subcore.id,
                'subcore_index': subcore.subcore_index,
                'title': subcore.title,
                'lead_user_id': subcore.lead_user_id,
                'lead_username': subcore.lead_user.username if subcore.lead_user else None,
                'lead_display_name': subcore.lead_user.display_name if subcore.lead_user else None,
                'slots': slots_payload,
                'total_slots': len(slots_payload)
            })

        total_core_slots = sum(len(sc['slots']) for sc in subcores_payload)
        payload.append({
            'id': core.id,
            'core_index': core.core_index,
            'title': core.title,
            'lead_user_id': core.lead_user_id,
            'lead_username': core.lead_user.username if core.lead_user else None,
            'lead_display_name': core.lead_user.display_name if core.lead_user else None,
            'subcores': subcores_payload,
            'total_slots': total_core_slots
        })

    return payload


def get_user_applications(owner_username, user_id=None):
    """Возвращает полный список анкет пользователя по всем типам, включая реферальные заявки."""
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

    # Реферальные заявки стримерш/моделей, привязанные к пользователю
    if user_id is not None:
        referred_models = ScoutJoinApplication.query.filter(
            db.or_(
                ScoutJoinApplication.referred_by_user_id == user_id,
                ScoutJoinApplication.referred_by_username == username
            )
        ).all()
    else:
        referred_models = ScoutJoinApplication.query.filter_by(referred_by_username=username).all()

    for row in referred_models:
        items.append({
            'kind': 'model_ref',
            'kind_label': 'Модель (реферальная)',
            'id': row.id,
            'full_name': row.full_name,
            'status': row.status or 'pending',
            'team': row.team,
            'contact': row.telegram_username or row.email or '-',
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
        ref_code_raw = (request.form.get('ref_code') or '').strip()
        referrer_user, normalized_ref_code = resolve_referrer_user(ref_code_raw)

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
            ref_code=normalized_ref_code or None,
            referred_by_user_id=referrer_user.id if referrer_user else None,
            referred_by_username=referrer_user.username if referrer_user else None,
            team=referrer_user.team if referrer_user and referrer_user.team else None,
            work_time=f'{work_hours_per_week}'  # Сохраняем для совместимости
        )

        db.session.add(application)
        db.session.commit()
        
        response_data = {
            'success': True,
            'message': 'Анкета отправлена'
        }
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
    if not can_access_admin_panel(user):
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
    if LOGIN_ACCESS_RESTRICTED:
        if request.method == 'POST':
            audit_logger.warning(
                'LOGIN_BLOCKED actor=%s action=login_blocked event="%s" ip=%s ua="%s"',
                request.form.get('username'),
                _safe_log_text(LOGIN_ACCESS_RESTRICTED_MESSAGE),
                request.headers.get('X-Forwarded-For', request.remote_addr),
                _truncate_value(request.user_agent.string, limit=180)
            )
            flash(LOGIN_ACCESS_RESTRICTED_MESSAGE, 'error')
        return render_template(
            'login.html',
            access_restricted=True,
            restricted_message=LOGIN_ACCESS_RESTRICTED_MESSAGE
        )

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
    return render_template(
        'login.html',
        access_restricted=False,
        restricted_message=LOGIN_ACCESS_RESTRICTED_MESSAGE
    )


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

    referred_models_total = ScoutJoinApplication.query.filter_by(referred_by_user_id=user.id).count()
    referred_models_approved = ScoutJoinApplication.query.filter_by(referred_by_user_id=user.id, status='approved').count()
    referred_models_rejected = ScoutJoinApplication.query.filter_by(referred_by_user_id=user.id, status='rejected').count()

    stats = {
        'applicants_count': operator_total + model_total + referred_models_total + chatter_total,
        'approved_applicants': operator_approved + model_approved + referred_models_approved + chatter_approved,
        'rejected_applicants': operator_rejected + model_rejected + referred_models_rejected + chatter_rejected,
        'operators_total': operator_total,
        'operators_approved': operator_approved,
        'operators_rejected': operator_rejected,
        'models_total': model_total + referred_models_total,
        'models_approved': model_approved + referred_models_approved,
        'models_rejected': model_rejected + referred_models_rejected,
        'chatters_total': chatter_total,
        'chatters_approved': chatter_approved,
        'chatters_rejected': chatter_rejected,
        'referred_models_total': referred_models_total,
        'referred_models_approved': referred_models_approved,
        'referred_models_rejected': referred_models_rejected
    }

    my_applications = get_user_applications(user.username, user.id)
    referral_url = f"{url_for('index', _external=True)}?ref={user.ref_token or user.username}"
    team_structure = get_user_team_structure_position(user)
    return render_template(
        'profile.html',
        current_user=user,
        stats=stats,
        is_admin_view=False,
        my_applications=my_applications,
        referral_url=referral_url,
        team_structure=team_structure
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

    referred_models_total = ScoutJoinApplication.query.filter_by(referred_by_user_id=user.id).count()
    referred_models_approved = ScoutJoinApplication.query.filter_by(referred_by_user_id=user.id, status='approved').count()
    referred_models_rejected = ScoutJoinApplication.query.filter_by(referred_by_user_id=user.id, status='rejected').count()

    stats = {
        'applicants_count': operator_total + model_total + referred_models_total + chatter_total,
        'approved_applicants': operator_approved + model_approved + referred_models_approved + chatter_approved,
        'rejected_applicants': operator_rejected + model_rejected + referred_models_rejected + chatter_rejected,
        'operators_total': operator_total,
        'operators_approved': operator_approved,
        'operators_rejected': operator_rejected,
        'models_total': model_total + referred_models_total,
        'models_approved': model_approved + referred_models_approved,
        'models_rejected': model_rejected + referred_models_rejected,
        'chatters_total': chatter_total,
        'chatters_approved': chatter_approved,
        'chatters_rejected': chatter_rejected,
        'referred_models_total': referred_models_total,
        'referred_models_approved': referred_models_approved,
        'referred_models_rejected': referred_models_rejected
    }

    my_applications = get_user_applications(user.username, user.id)
    referral_url = f"{url_for('index', _external=True)}?ref={user.ref_token or user.username}"
    team_structure = get_user_team_structure_position(user)
    return render_template(
        'profile.html',
        current_user=user,
        stats=stats,
        is_admin_view=True,
        admin_user=admin,
        my_applications=my_applications,
        referral_url=referral_url,
        team_structure=team_structure
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


def _get_or_create_team_stats_demo_user(team_name, team_index):
    username = f'demo_stats_team_{team_index}'
    user = User.query.filter_by(username=username).first()
    if user:
        if user.team != team_name:
            user.team = team_name
        return user, False

    user = User(
        username=username,
        password_hash=generate_password_hash(f'demo-{team_index}-stats'),
        display_name=f'Демо {team_name}',
        team=team_name,
        ref_token=f'demo_stats_{team_index:02d}'
    )
    db.session.add(user)
    db.session.flush()
    return user, True


def _seed_team_stats_demo_data():
    now = moscow_now()
    created = {
        'users': 0,
        'operators': 0,
        'models': 0,
        'scouts': 0
    }

    for team_index, team_name in enumerate(VALID_TEAMS, start=1):
        demo_user, user_created = _get_or_create_team_stats_demo_user(team_name, team_index)
        if user_created:
            created['users'] += 1

        operator_specs = [
            ('approved', 0, 'Оператор'),
            ('pending', 3, 'Оператор'),
            ('rejected', 15, 'Оператор')
        ]
        for item_index, (status, days_ago, role_label) in enumerate(operator_specs, start=1):
            full_name = f'DEMO {team_name} {role_label} {item_index}'
            exists = Applicant.query.filter_by(owner_username=demo_user.username, full_name=full_name).first()
            if exists:
                continue

            db.session.add(Applicant(
                full_name=full_name,
                date_of_birth='01.01.2000',
                english_level='B1',
                cpu_model='Ryzen 5',
                gpu_model='RTX 3060',
                internet_speed='250 Mbps',
                work_experience='Демо-запись для статистики',
                interview_time='18:00',
                phone=f'+7999000{team_index:02d}{item_index:02d}',
                telegram=f'@demo_{team_index}_{item_index}_operator',
                owner_username=demo_user.username,
                status=status,
                team=team_name,
                date_added=now - timedelta(days=days_ago, hours=item_index)
            ))
            created['operators'] += 1

        model_specs = [
            ('approved', 0, 'Модель'),
            ('pending', 4, 'Модель')
        ]
        for item_index, (status, days_ago, role_label) in enumerate(model_specs, start=1):
            full_name = f'DEMO {team_name} {role_label} {item_index}'
            exists = ModelOperatorApplication.query.filter_by(owner_username=demo_user.username, full_name=full_name).first()
            if exists:
                continue

            db.session.add(ModelOperatorApplication(
                full_name=full_name,
                city='Москва',
                phone=f'+7888000{team_index:02d}{item_index:02d}',
                age='22',
                residence='одна',
                has_dual_devices='да',
                device_model='iPhone + PC',
                work_hours='5/2 по 8 часов',
                has_headphones='да',
                telegram=f'@demo_{team_index}_{item_index}_model',
                interview_time='16:30',
                photos='',
                owner_username=demo_user.username,
                status=status,
                team=team_name,
                date_added=now - timedelta(days=days_ago, hours=team_index)
            ))
            created['models'] += 1

        scout_specs = [
            ('approved', 1, 'Стримерша'),
            ('rejected', 12, 'Стримерша')
        ]
        for item_index, (status, days_ago, role_label) in enumerate(scout_specs, start=1):
            full_name = f'DEMO {team_name} {role_label} {item_index}'
            exists = ScoutJoinApplication.query.filter_by(referred_by_user_id=demo_user.id, full_name=full_name).first()
            if exists:
                continue

            db.session.add(ScoutJoinApplication(
                full_name=full_name,
                age='21',
                city='Санкт-Петербург',
                motivation='Демо-запись для проверки командной статистики',
                telegram_username=f'demo_{team_index}_{item_index}_scout',
                work_time='4 часа в день',
                can_stream_change='yes',
                device_model='iPhone 14',
                work_hours_per_week='20',
                referred_by_user_id=demo_user.id,
                referred_by_username=demo_user.username,
                status=status,
                team=team_name,
                date_added=now - timedelta(days=days_ago, hours=item_index)
            ))
            created['scouts'] += 1

    db.session.commit()
    return created


@app.route('/api/admin/team-stats/demo-seed', methods=['POST'])
def admin_seed_team_stats_demo():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    user = User.query.get(session['user_id'])
    if not can_access_team_stats_tab(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    try:
        created = _seed_team_stats_demo_data()
        total_created = sum(created.values())
        if total_created == 0:
            message = 'Демо-анкеты уже существуют, новые записи не добавлялись'
        else:
            message = (
                f"Добавлено: пользователей {created['users']}, операторских анкет {created['operators']}, "
                f"модельных анкет {created['models']}, стримерских анкет {created['scouts']}"
            )
        return jsonify({'success': True, 'message': message, 'created': created}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/team-stats')
def get_admin_team_stats():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    user = User.query.get(session['user_id'])
    if not can_access_team_stats_tab(user):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    period_key = (request.args.get('period', 'day') or 'day').strip().lower()
    period_map = {
        'day': ('За день', timedelta(days=1)),
        'week': ('За неделю', timedelta(days=7)),
        'month': ('За месяц', timedelta(days=30))
    }
    if period_key not in period_map:
        period_key = 'day'

    period_label, period_delta = period_map[period_key]
    since_dt = moscow_now() - period_delta

    selected_team = (request.args.get('team', '') or '').strip()
    if selected_team and selected_team not in VALID_TEAMS:
        return jsonify({'success': False, 'message': 'Неверная команда'}), 400

    scope_key = (request.args.get('scope', 'team') or 'team').strip().lower()
    if scope_key not in {'team', 'core', 'subcore'}:
        scope_key = 'team'

    try:
        selected_core_id = int(request.args.get('core_id')) if request.args.get('core_id') else None
    except Exception:
        selected_core_id = None
    try:
        selected_subcore_id = int(request.args.get('subcore_id')) if request.args.get('subcore_id') else None
    except Exception:
        selected_subcore_id = None

    if not selected_team:
        selected_team = VALID_TEAMS[0] if VALID_TEAMS else ''

    nav_teams = [
        {'team': team_name, 'emoji': TEAM_EMOJI_MAP.get(team_name, '🎯')}
        for team_name in VALID_TEAMS
    ]

    cores = TeamCore.query.filter_by(team_name=selected_team).order_by(TeamCore.core_index.asc()).all()
    scope_options = {
        'cores': [
            {
                'id': core.id,
                'core_index': core.core_index,
                'title': core.title,
                'subcores': [
                    {
                        'id': sub.id,
                        'subcore_index': sub.subcore_index,
                        'title': sub.title
                    }
                    for sub in TeamSubCore.query.filter_by(core_id=core.id).order_by(TeamSubCore.subcore_index.asc()).all()
                ]
            }
            for core in cores
        ]
    }

    def _to_team_payload(team_name, stats):
        operators_total = int((stats or {}).get('operators_total', 0))
        operators_approved = int((stats or {}).get('operators_approved', 0))
        operators_rejected = int((stats or {}).get('operators_rejected', 0))
        operators_pending = int((stats or {}).get('operators_pending', max(operators_total - operators_approved - operators_rejected, 0)))

        models_total = int((stats or {}).get('models_total', 0))
        models_approved = int((stats or {}).get('models_approved', 0))
        models_rejected = int((stats or {}).get('models_rejected', 0))
        models_pending = int((stats or {}).get('models_pending', max(models_total - models_approved - models_rejected, 0)))

        return {
            'team': team_name,
            'emoji': TEAM_EMOJI_MAP.get(team_name, '🎯'),
            'operators': {
                'total': operators_total,
                'approved': operators_approved,
                'rejected': operators_rejected,
                'pending': max(operators_pending, 0)
            },
            'models': {
                'total': models_total,
                'approved': models_approved,
                'rejected': models_rejected,
                'pending': max(models_pending, 0)
            }
        }

    teams_payload = []
    scope_label = 'Вся команда'

    if scope_key == 'team':
        for team_name in VALID_TEAMS:
            team_stats = _calculate_team_panel_stats(
                team_name=team_name,
                scope='team',
                since_dt=since_dt
            )
            teams_payload.append(_to_team_payload(team_name, team_stats))
        scope_label = 'Вся команда'
    else:
        selected_stats = _calculate_team_panel_stats(
            team_name=selected_team,
            scope=scope_key,
            core_id=selected_core_id,
            subcore_id=selected_subcore_id,
            since_dt=since_dt
        )
        scope_label = selected_stats.get('scope_label', 'Вся команда')
        teams_payload.append(_to_team_payload(selected_team, selected_stats))

    return jsonify({
        'success': True,
        'period': period_key,
        'period_label': period_label,
        'scope': scope_key,
        'scope_label': scope_label,
        'selected_team': selected_team,
        'selected_core_id': selected_core_id,
        'selected_subcore_id': selected_subcore_id,
        'scope_options': scope_options,
        'nav_teams': nav_teams,
        'teams': teams_payload
    })


@app.route('/team-panel')
def team_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    # Fail-safe: владелец и developer всегда проходят в панель команды.
    force_full_team_panel_access = bool(user.is_owner or is_developer_user(user))

    can_access = can_access_team_panel(user)
    managed_teams = sorted(get_user_managed_teams(user))
    audit_logger.info(
        'TEAM_PANEL_ACCESS_CHECK actor=%s user_id=%s is_admin=%s is_owner=%s prefix=%s team=%s can_access=%s force_access=%s managed_teams=%s',
        user.username,
        user.id,
        bool(user.is_admin),
        bool(user.is_owner),
        (user.prefix or ''),
        (user.team or ''),
        bool(can_access),
        bool(force_full_team_panel_access),
        ','.join(managed_teams)
    )

    if not (can_access or force_full_team_panel_access):
        flash('Нет доступа к панели команды для текущего аккаунта', 'error')
        return redirect(url_for('dashboard'))

    requested_team = request.args.get('team', '')
    team_name = resolve_team_for_panel(user, requested_team=requested_team)
    if not team_name:
        flash('Назначьте команду администратору, чтобы открыть панель команды', 'error')
        return redirect(url_for('admin_panel'))

    can_edit_structure = can_access or force_full_team_panel_access

    ensure_team_structure_seed(team_name=team_name)

    team_users = User.query.filter_by(team=team_name).order_by(User.username.asc()).all()
    structure = build_team_structure_payload(team_name)

    stats = _calculate_team_panel_stats(team_name=team_name, scope='team')

    response = make_response(render_template(
        'team_panel.html',
        current_user=user,
        team_name=team_name,
        valid_teams=sorted(get_user_managed_teams(user)),
        can_edit_structure=can_edit_structure,
        stats=stats,
        structure=structure,
        team_users=team_users,
        team_users_json=[u.to_dict() for u in team_users]
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def _calculate_team_panel_stats(team_name, scope='team', core_id=None, subcore_id=None, since_dt=None):
    """Считает статистику панели по уровню: вся команда / основа / под-основа."""
    scope_key = (scope or 'team').strip().lower()
    scope_label = 'Вся команда'

    core = None
    subcore = None

    if scope_key == 'core':
        core = TeamCore.query.filter_by(id=core_id, team_name=team_name).first()
        if not core:
            scope_key = 'team'
        else:
            scope_label = f'Основа {core.core_index}'

    if scope_key == 'subcore':
        subcore = TeamSubCore.query.join(TeamCore, TeamCore.id == TeamSubCore.core_id).filter(
            TeamSubCore.id == subcore_id,
            TeamCore.team_name == team_name
        ).first()
        if not subcore:
            scope_key = 'team'
        else:
            core = TeamCore.query.get(subcore.core_id)
            scope_label = f'Под-основа {core.core_index}.{subcore.subcore_index}' if core else 'Под-основа'

    slots_query = TeamAcademSlot.query.join(TeamSubCore, TeamSubCore.id == TeamAcademSlot.subcore_id).join(
        TeamCore, TeamCore.id == TeamSubCore.core_id
    ).filter(TeamCore.team_name == team_name)

    if scope_key == 'core' and core:
        slots_query = slots_query.filter(TeamCore.id == core.id)
    elif scope_key == 'subcore' and subcore:
        slots_query = slots_query.filter(TeamSubCore.id == subcore.id)

    total_slots = slots_query.count()
    assigned_slots = slots_query.filter(TeamAcademSlot.user_id.isnot(None)).count()

    if scope_key == 'team':
        member_users = User.query.filter_by(team=team_name).all()
    elif scope_key == 'core' and core:
        member_ids = set()
        if core.lead_user_id:
            member_ids.add(core.lead_user_id)
        subcores = TeamSubCore.query.filter_by(core_id=core.id).all()
        for sub in subcores:
            if sub.lead_user_id:
                member_ids.add(sub.lead_user_id)
        slot_user_ids = db.session.query(TeamAcademSlot.user_id).join(
            TeamSubCore, TeamSubCore.id == TeamAcademSlot.subcore_id
        ).filter(
            TeamSubCore.core_id == core.id,
            TeamAcademSlot.user_id.isnot(None)
        ).all()
        for (uid,) in slot_user_ids:
            if uid:
                member_ids.add(uid)
        member_users = User.query.filter(User.id.in_(list(member_ids))).all() if member_ids else []
    elif scope_key == 'subcore' and subcore:
        member_ids = set()
        if subcore.lead_user_id:
            member_ids.add(subcore.lead_user_id)
        slot_user_ids = db.session.query(TeamAcademSlot.user_id).filter(
            TeamAcademSlot.subcore_id == subcore.id,
            TeamAcademSlot.user_id.isnot(None)
        ).all()
        for (uid,) in slot_user_ids:
            if uid:
                member_ids.add(uid)
        member_users = User.query.filter(User.id.in_(list(member_ids))).all() if member_ids else []
    else:
        member_users = User.query.filter_by(team=team_name).all()
        scope_key = 'team'
        scope_label = 'Вся команда'

    member_usernames = [u.username for u in member_users if u and u.username]
    member_user_ids = [u.id for u in member_users if u and u.id]

    if member_usernames:
        operators_query = Applicant.query.filter(
            Applicant.owner_username.in_(member_usernames),
            Applicant.is_deleted == False
        )
        if since_dt is not None:
            operators_query = operators_query.filter(Applicant.date_added >= since_dt)

        operators_total = operators_query.count()
        operators_approved = operators_query.filter(Applicant.status == 'approved').count()
        operators_rejected = operators_query.filter(Applicant.status == 'rejected').count()

        models_regular_query = ModelOperatorApplication.query.filter(
            ModelOperatorApplication.owner_username.in_(member_usernames),
            ModelOperatorApplication.is_deleted != True
        )
        if since_dt is not None:
            models_regular_query = models_regular_query.filter(ModelOperatorApplication.date_added >= since_dt)

        models_regular_total = models_regular_query.count()
        models_regular_approved = models_regular_query.filter(ModelOperatorApplication.status == 'approved').count()
        models_regular_rejected = models_regular_query.filter(ModelOperatorApplication.status == 'rejected').count()

        chatters_query = ChatApplication.query.filter(
            ChatApplication.owner_username.in_(member_usernames),
            ChatApplication.is_deleted != True
        )
        if since_dt is not None:
            chatters_query = chatters_query.filter(ChatApplication.date_added >= since_dt)

        chatters_total = chatters_query.count()
        chatters_approved = chatters_query.filter(ChatApplication.status == 'approved').count()
        chatters_rejected = chatters_query.filter(ChatApplication.status == 'rejected').count()
    else:
        operators_total = 0
        operators_approved = 0
        operators_rejected = 0
        models_regular_total = 0
        models_regular_approved = 0
        models_regular_rejected = 0
        chatters_total = 0
        chatters_approved = 0
        chatters_rejected = 0

    if member_user_ids or member_usernames:
        scout_filter = [ScoutJoinApplication.is_deleted != True]
        if member_user_ids and member_usernames:
            scout_filter.append(db.or_(
                ScoutJoinApplication.referred_by_user_id.in_(member_user_ids),
                ScoutJoinApplication.referred_by_username.in_(member_usernames)
            ))
        elif member_user_ids:
            scout_filter.append(ScoutJoinApplication.referred_by_user_id.in_(member_user_ids))
        else:
            scout_filter.append(ScoutJoinApplication.referred_by_username.in_(member_usernames))

        if since_dt is not None:
            scout_filter.append(ScoutJoinApplication.date_added >= since_dt)

        scout_total = ScoutJoinApplication.query.filter(*scout_filter).count()
        scout_approved = ScoutJoinApplication.query.filter(*scout_filter, ScoutJoinApplication.status == 'approved').count()
        scout_rejected = ScoutJoinApplication.query.filter(*scout_filter, ScoutJoinApplication.status == 'rejected').count()
    else:
        scout_total = 0
        scout_approved = 0
        scout_rejected = 0

    operators_pending = max(operators_total - operators_approved - operators_rejected, 0)
    models_total = models_regular_total + scout_total
    models_approved = models_regular_approved + scout_approved
    models_rejected = models_regular_rejected + scout_rejected
    models_pending = max(models_total - models_approved - models_rejected, 0)
    chatters_pending = max(chatters_total - chatters_approved - chatters_rejected, 0)

    return {
        'team_name': team_name,
        'team_emoji': TEAM_EMOJI_MAP.get(team_name, '🎯'),
        'scope': scope_key,
        'scope_label': scope_label,
        'total_slots': total_slots,
        'assigned_slots': assigned_slots,
        'free_slots': max(0, total_slots - assigned_slots),
        'team_users_count': len(member_users),
        'admins_count': sum(1 for u in member_users if u.is_admin),
        'workers_count': sum(1 for u in member_users if not u.is_admin),
        'operators_total': operators_total,
        'operators_approved': operators_approved,
        'operators_rejected': operators_rejected,
        'operators_pending': operators_pending,
        'models_total': models_total,
        'models_approved': models_approved,
        'models_rejected': models_rejected,
        'models_pending': models_pending,
        'chatters_total': chatters_total,
        'chatters_approved': chatters_approved,
        'chatters_rejected': chatters_rejected,
        'chatters_pending': chatters_pending
    }


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
        team=team,
        ref_token=secrets.token_hex(8)
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
        valid_teams = VALID_TEAMS + ['']
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


@app.route('/api/team-panel/data')
def team_panel_data():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    team_name = resolve_team_for_panel(actor, requested_team=request.args.get('team', ''))
    if not team_name:
        return jsonify({'success': False, 'message': 'Команда не назначена'}), 400

    ensure_team_structure_seed(team_name=team_name)

    structure = build_team_structure_payload(team_name)
    team_users = User.query.filter_by(team=team_name).order_by(User.username.asc()).all()

    return jsonify({
        'success': True,
        'team_name': team_name,
        'structure': structure,
        'team_users': [u.to_dict() for u in team_users],
        'can_edit_structure': can_access_team_panel(actor)
    }), 200


@app.route('/api/team-panel/stats')
def team_panel_stats():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    team_name = resolve_team_for_panel(actor, requested_team=request.args.get('team', ''))
    if not team_name:
        return jsonify({'success': False, 'message': 'Команда не назначена'}), 400

    scope = (request.args.get('scope') or 'team').strip().lower()
    core_id_raw = request.args.get('core_id')
    subcore_id_raw = request.args.get('subcore_id')

    try:
        core_id = int(core_id_raw) if core_id_raw else None
    except Exception:
        core_id = None
    try:
        subcore_id = int(subcore_id_raw) if subcore_id_raw else None
    except Exception:
        subcore_id = None

    stats = _calculate_team_panel_stats(
        team_name=team_name,
        scope=scope,
        core_id=core_id,
        subcore_id=subcore_id
    )

    return jsonify({
        'success': True,
        'team_name': team_name,
        'stats': stats
    }), 200


@app.route('/api/team-panel/slot/assign', methods=['POST'])
def assign_team_panel_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    slot_id = data.get('slot_id')
    user_id = data.get('user_id')

    if not slot_id or not user_id:
        return jsonify({'success': False, 'message': 'slot_id и user_id обязательны'}), 400

    slot = TeamAcademSlot.query.get(slot_id)
    target_user = User.query.get(user_id)
    if not slot or not target_user:
        return jsonify({'success': False, 'message': 'Слот или пользователь не найден'}), 404

    subcore = TeamSubCore.query.get(slot.subcore_id)
    core = TeamCore.query.get(subcore.core_id) if subcore else None
    if not core:
        return jsonify({'success': False, 'message': 'Структура команды повреждена'}), 400

    if not can_manage_subcore(actor, subcore):
        return jsonify({'success': False, 'message': 'Нет прав управлять этой под-основой'}), 403

    if target_user.team != core.team_name:
        return jsonify({'success': False, 'message': 'Пользователь должен состоять в этой команде'}), 400

    busy_message = _find_busy_assignment_in_team(
        team_name=core.team_name,
        user_id=target_user.id,
        exclude_slot_id=slot.id
    )
    if busy_message:
        return jsonify({'success': False, 'message': busy_message}), 400

    slot.user_id = target_user.id
    slot.assigned_at = moscow_now()
    db.session.commit()

    return jsonify({'success': True, 'message': 'Пользователь назначен в слот'}), 200


@app.route('/api/team-panel/slot/clear', methods=['POST'])
def clear_team_panel_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    slot_id = data.get('slot_id')
    if not slot_id:
        return jsonify({'success': False, 'message': 'slot_id обязателен'}), 400

    slot = TeamAcademSlot.query.get(slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Слот не найден'}), 404

    subcore = TeamSubCore.query.get(slot.subcore_id)
    core = TeamCore.query.get(subcore.core_id) if subcore else None
    if not core:
        return jsonify({'success': False, 'message': 'Структура команды повреждена'}), 400

    if not can_manage_subcore(actor, subcore):
        return jsonify({'success': False, 'message': 'Нет прав управлять этой под-основой'}), 403

    slot.user_id = None
    slot.assigned_at = None
    db.session.commit()

    return jsonify({'success': True, 'message': 'Слот очищен'}), 200


def _validate_team_panel_target_user(actor, team_name, user_id):
    target_user = User.query.get(user_id)
    if not target_user:
        return None, (jsonify({'success': False, 'message': 'Пользователь не найден'}), 404)

    if team_name not in get_user_managed_teams(actor):
        return None, (jsonify({'success': False, 'message': 'Нет доступа к этой команде'}), 403)

    if target_user.team != team_name:
        return None, (jsonify({'success': False, 'message': 'Пользователь должен состоять в этой команде'}), 400)

    return target_user, None


def _find_busy_assignment_in_team(team_name, user_id, exclude_slot_id=None, exclude_core_id=None, exclude_subcore_id=None):
    slot_query = TeamAcademSlot.query.join(TeamSubCore, TeamSubCore.id == TeamAcademSlot.subcore_id).join(
        TeamCore, TeamCore.id == TeamSubCore.core_id
    ).filter(
        TeamCore.team_name == team_name,
        TeamAcademSlot.user_id == user_id
    )
    if exclude_slot_id:
        slot_query = slot_query.filter(TeamAcademSlot.id != exclude_slot_id)
    if slot_query.first():
        return 'Пользователь уже назначен в другой слот'

    core_query = TeamCore.query.filter(
        TeamCore.team_name == team_name,
        TeamCore.lead_user_id == user_id
    )
    if exclude_core_id:
        core_query = core_query.filter(TeamCore.id != exclude_core_id)
    if core_query.first():
        return 'Пользователь уже назначен ответственным за основу'

    subcore_query = TeamSubCore.query.join(TeamCore, TeamCore.id == TeamSubCore.core_id).filter(
        TeamCore.team_name == team_name,
        TeamSubCore.lead_user_id == user_id
    )
    if exclude_subcore_id:
        subcore_query = subcore_query.filter(TeamSubCore.id != exclude_subcore_id)
    if subcore_query.first():
        return 'Пользователь уже назначен ответственным за под-основу'

    return None


@app.route('/api/team-panel/core/assign', methods=['POST'])
def assign_team_panel_core_lead():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    core_id = data.get('core_id')
    user_id = data.get('user_id')
    if not core_id or not user_id:
        return jsonify({'success': False, 'message': 'core_id и user_id обязательны'}), 400

    core = TeamCore.query.get(core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404

    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может назначать лидера основы'}), 403

    target_user, error_response = _validate_team_panel_target_user(actor, core.team_name, user_id)
    if error_response:
        return error_response

    busy_message = _find_busy_assignment_in_team(
        team_name=core.team_name,
        user_id=target_user.id,
        exclude_core_id=core.id
    )
    if busy_message:
        return jsonify({'success': False, 'message': busy_message}), 400

    core.lead_user_id = target_user.id
    db.session.commit()
    return jsonify({'success': True, 'message': 'Ответственный за основу назначен'}), 200


@app.route('/api/team-panel/core/clear', methods=['POST'])
def clear_team_panel_core_lead():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    core_id = data.get('core_id')
    if not core_id:
        return jsonify({'success': False, 'message': 'core_id обязателен'}), 400

    core = TeamCore.query.get(core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404

    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может снимать лидера основы'}), 403

    core.lead_user_id = None
    db.session.commit()
    return jsonify({'success': True, 'message': 'Ответственный за основу снят'}), 200


@app.route('/api/team-panel/subcore/assign', methods=['POST'])
def assign_team_panel_subcore_lead():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    subcore_id = data.get('subcore_id')
    user_id = data.get('user_id')
    if not subcore_id or not user_id:
        return jsonify({'success': False, 'message': 'subcore_id и user_id обязательны'}), 400

    subcore = TeamSubCore.query.get(subcore_id)
    if not subcore:
        return jsonify({'success': False, 'message': 'Под-основа не найдена'}), 404

    core = TeamCore.query.get(subcore.core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404

    if not can_manage_core(actor, core):
        return jsonify({'success': False, 'message': 'Нет прав управлять этой основой'}), 403

    target_user, error_response = _validate_team_panel_target_user(actor, core.team_name, user_id)
    if error_response:
        return error_response

    busy_message = _find_busy_assignment_in_team(
        team_name=core.team_name,
        user_id=target_user.id,
        exclude_subcore_id=subcore.id
    )
    if busy_message:
        return jsonify({'success': False, 'message': busy_message}), 400

    subcore.lead_user_id = target_user.id
    db.session.commit()
    return jsonify({'success': True, 'message': 'Ответственный за под-основу назначен'}), 200


@app.route('/api/team-panel/subcore/clear', methods=['POST'])
def clear_team_panel_subcore_lead():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    subcore_id = data.get('subcore_id')
    if not subcore_id:
        return jsonify({'success': False, 'message': 'subcore_id обязателен'}), 400

    subcore = TeamSubCore.query.get(subcore_id)
    if not subcore:
        return jsonify({'success': False, 'message': 'Под-основа не найдена'}), 404

    core = TeamCore.query.get(subcore.core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404

    if not can_manage_core(actor, core):
        return jsonify({'success': False, 'message': 'Нет прав управлять этой основой'}), 403

    subcore.lead_user_id = None
    db.session.commit()
    return jsonify({'success': True, 'message': 'Ответственный за под-основу снят'}), 200


@app.route('/api/team-panel/core/create', methods=['POST'])
def create_team_panel_core():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    team_name = resolve_team_for_panel(actor, requested_team=(request.get_json(silent=True) or {}).get('team'))
    if not team_name:
        return jsonify({'success': False, 'message': 'Команда не найдена'}), 400
    if not can_administer_team(actor, team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может создавать основу'}), 403

    max_core_index = db.session.query(db.func.max(TeamCore.core_index)).filter_by(team_name=team_name).scalar() or 0
    next_core_index = int(max_core_index) + 1

    core = TeamCore(team_name=team_name, core_index=next_core_index, title=f'Основа {next_core_index}')
    db.session.add(core)
    db.session.flush()

    subcore = TeamSubCore(core_id=core.id, subcore_index=1, title=f'Под-основа {next_core_index}.1')
    db.session.add(subcore)
    db.session.flush()

    db.session.add(TeamAcademSlot(subcore_id=subcore.id, slot_index=1))
    db.session.commit()

    return jsonify({'success': True, 'message': f'Основа {next_core_index} создана'}), 200


@app.route('/api/team-panel/core/delete', methods=['POST'])
def delete_team_panel_core():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    core_id = data.get('core_id')
    if not core_id:
        return jsonify({'success': False, 'message': 'core_id обязателен'}), 400

    core = TeamCore.query.get(core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404
    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может удалять основу'}), 403

    cores_count = TeamCore.query.filter_by(team_name=core.team_name).count()
    if cores_count <= 1:
        return jsonify({'success': False, 'message': 'Нельзя удалить последнюю основу в команде'}), 400

    team_name = core.team_name
    db.session.delete(core)
    db.session.flush()
    renumber_team_structure(team_name)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Основа удалена'}), 200


@app.route('/api/team-panel/subcore/create', methods=['POST'])
def create_team_panel_subcore():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    core_id = data.get('core_id')
    if not core_id:
        return jsonify({'success': False, 'message': 'core_id обязателен'}), 400

    core = TeamCore.query.get(core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404
    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может создавать под-основы'}), 403

    max_subcore_index = db.session.query(db.func.max(TeamSubCore.subcore_index)).filter_by(core_id=core.id).scalar() or 0
    next_subcore_index = int(max_subcore_index) + 1
    subcore = TeamSubCore(
        core_id=core.id,
        subcore_index=next_subcore_index,
        title=f'Под-основа {core.core_index}.{next_subcore_index}'
    )
    db.session.add(subcore)
    db.session.flush()

    db.session.add(TeamAcademSlot(subcore_id=subcore.id, slot_index=1))
    db.session.commit()

    return jsonify({'success': True, 'message': f'Под-основа {core.core_index}.{next_subcore_index} создана'}), 200


@app.route('/api/team-panel/subcore/delete', methods=['POST'])
def delete_team_panel_subcore():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    subcore_id = data.get('subcore_id')
    if not subcore_id:
        return jsonify({'success': False, 'message': 'subcore_id обязателен'}), 400

    subcore = TeamSubCore.query.get(subcore_id)
    if not subcore:
        return jsonify({'success': False, 'message': 'Под-основа не найдена'}), 404

    core = TeamCore.query.get(subcore.core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404
    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может удалять под-основу'}), 403

    subcores_count = TeamSubCore.query.filter_by(core_id=core.id).count()
    if subcores_count <= 1:
        return jsonify({'success': False, 'message': 'Нельзя удалить последнюю под-основу в основе'}), 400

    db.session.delete(subcore)
    db.session.flush()
    renumber_team_structure(core.team_name)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Под-основа удалена'}), 200


@app.route('/api/team-panel/slot/create', methods=['POST'])
def create_team_panel_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    subcore_id = data.get('subcore_id')
    if not subcore_id:
        return jsonify({'success': False, 'message': 'subcore_id обязателен'}), 400

    subcore = TeamSubCore.query.get(subcore_id)
    if not subcore:
        return jsonify({'success': False, 'message': 'Под-основа не найдена'}), 404

    core = TeamCore.query.get(subcore.core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404
    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может создавать академ-слоты'}), 403

    max_slot_index = db.session.query(db.func.max(TeamAcademSlot.slot_index)).filter_by(subcore_id=subcore.id).scalar() or 0
    next_slot_index = int(max_slot_index) + 1
    db.session.add(TeamAcademSlot(subcore_id=subcore.id, slot_index=next_slot_index))
    db.session.commit()

    return jsonify({'success': True, 'message': f'Академ {next_slot_index} создан'}), 200


@app.route('/api/team-panel/slot/delete', methods=['POST'])
def delete_team_panel_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    actor = User.query.get(session['user_id'])
    if not can_access_team_panel(actor):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json() or {}
    slot_id = data.get('slot_id')
    if not slot_id:
        return jsonify({'success': False, 'message': 'slot_id обязателен'}), 400

    slot = TeamAcademSlot.query.get(slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Слот не найден'}), 404

    subcore = TeamSubCore.query.get(slot.subcore_id)
    if not subcore:
        return jsonify({'success': False, 'message': 'Под-основа не найдена'}), 404
    core = TeamCore.query.get(subcore.core_id)
    if not core:
        return jsonify({'success': False, 'message': 'Основа не найдена'}), 404
    if not can_administer_team(actor, core.team_name):
        return jsonify({'success': False, 'message': 'Только админ команды может удалять академ-слоты'}), 403

    slots_count = TeamAcademSlot.query.filter_by(subcore_id=subcore.id).count()
    if slots_count <= 1:
        return jsonify({'success': False, 'message': 'Нельзя удалить последний академ-слот в под-основе'}), 400

    db.session.delete(slot)
    db.session.flush()
    renumber_team_structure(core.team_name)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Академ-слот удален'}), 200

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
